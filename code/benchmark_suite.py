"""Repeatable, paid end-to-end LiveKit benchmark using fixed synthetic PCM clips.

Run inside benchmark-agent. Credentials are read only from environment/stdin.
Generate fixtures once, then reuse them unchanged for every configuration.
"""
import argparse
import array
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from livekit import rtc
from openai import AsyncOpenAI

PHRASES = {
    'dictation': 'Запиши пожалуйста завтра я позвоню Алексею и расскажу ему хорошие новости.',
    'first': 'Расскажи пожалуйста',
    'second': 'какая погода в Москве?',
    'story': 'Расскажи длинную сказку про лес и приключения.',
    'interrupt': 'Подожди лучше скажи сколько дней в неделе.',
    'tool': 'Позвони Алексею.',
}
COMPLEX_PHRASES = {
    'dictation': 'Запиши пожалуйста: в следующую среду после обеда я хочу позвонить Алексею, узнать как себя чувствует его мама, а потом напомнить Ивану купить хлеб и молоко.',
    'first': 'Подскажи пожалуйста, если завтра пойдёт дождь и станет прохладнее,',
    'second': 'стоит ли мне брать с собой зонт и тёплую куртку?',
    'story': 'Расскажи длинную сказку про лес и приключения, чтобы её было интересно слушать перед сном.',
    'interrupt': 'Подожди, сказку пока не надо. Лучше скажи сколько дней в неделе и какой день наступает после среды.',
    'tool': 'Пожалуйста, позвони моему внуку Алексею, я хочу спросить как у него дела.',
}
PROFILES = {'baseline-v1': PHRASES, 'complex-v2': COMPLEX_PHRASES}
API = os.environ.get('BENCHMARK_API_URL', 'http://localhost:8000').rstrip('/')

async def fixtures(path, phrases, voice='alloy'):
    path.mkdir(parents=True, exist_ok=True)
    existing = json.loads((path / 'manifest.json').read_text()) if (path / 'manifest.json').exists() else {}
    client = AsyncOpenAI()
    manifest = dict(existing)
    for name, text in phrases.items():
        target = path / (name + '.pcm')
        if target.exists() and (name not in existing or existing[name].get('text') != text or existing[name].get('synthetic_voice', 'alloy') != voice or hashlib.sha256(target.read_bytes()).hexdigest() != existing[name]['sha256']):
            raise ValueError('Existing fixture is not verified; choose a new directory: '+name)
        if not target.exists():
            response = await client.audio.speech.create(model='tts-1', voice=voice, input=text, response_format='pcm')
            samples = array.array('h', response.content)
            first = next((i for i, value in enumerate(samples) if abs(value) > 260), 0)
            last = next((len(samples)-i for i, value in enumerate(reversed(samples)) if abs(value) > 260), len(samples))
            target.write_bytes(samples[max(0, first-1200):min(len(samples), last+1200)].tobytes())
        data = target.read_bytes()
        manifest[name] = {'text': text, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'format': 'pcm_s16le_24000_mono', 'synthetic_voice': voice}
        (path / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

async def send(source, pcm):
    for offset in range(0, len(pcm), 960):
        await source.capture_frame(rtc.AudioFrame(pcm[offset:offset+960].ljust(960, b'\0'), 24000, 1, 480))
        await asyncio.sleep(.02)

async def wait_for(predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(): return True
        await asyncio.sleep(.1)
    return bool(predicate())

def words(value):
    return re.findall(r'[а-яa-z0-9]+', value.lower().replace('ё', 'е'))

def wer(reference, actual):
    a, b = words(reference), words(actual)
    if not a: return None
    row = list(range(len(b)+1))
    for i, w in enumerate(a, 1):
        nxt = [i]
        for j, x in enumerate(b, 1):
            nxt.append(min(nxt[-1]+1, row[j]+1, row[j-1]+(w != x)))
        row = nxt
    return round(row[-1]/len(a), 3)

async def exercise(client, headers, config, clips, case, interrupt_delay=0, phrases=PHRASES, interrupt_timeout=70):
    response = await client.post(API + '/api/v1/benchmarks/voice', headers=headers, json={**config, 'benchmark_tools': case == 'tool'})
    response.raise_for_status()
    info = response.json(); room = rtc.Room(); ready = asyncio.Event(); events = []; audio = asyncio.Event(); readers = set(); start = time.monotonic(); audio_times = []
    @room.on('data_received')
    def receive(packet):
        if packet.topic != 'benchmark': return
        try: item = json.loads(packet.data)
        except (ValueError, UnicodeError): return
        item['elapsed_ms'] = round((time.monotonic()-start)*1000)
        events.append(item)
        if item.get('type') == 'ready': ready.set()
    @room.on('track_subscribed')
    def on_track(track, publication, participant):
        async def reader():
            async for frame in rtc.AudioStream(track):
                if max((abs(x) for x in frame.frame.data), default=0) > 300:
                    audio.set()
                    audio_times.append(round((time.monotonic()-start)*1000))
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            task = asyncio.create_task(reader()); readers.add(task); task.add_done_callback(readers.discard)
    def items(kind, role=None):
        return [x for x in events if x.get('type') == kind and (role is None or x.get('role') == role)]
    try:
        await room.connect(info['server_url'], info['participant_token'])
        source = rtc.AudioSource(24000, 1)
        track = rtc.LocalAudioTrack.create_audio_track('microphone', source)
        await room.local_participant.publish_track(track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))
        await asyncio.wait_for(ready.wait(), 40)
        await send(source, bytes(24000))
        if case.startswith('pause'):
            await send(source, clips['first']); await send(source, bytes(round((.2 if case == 'pause_short' else 1.5)*48000))); await send(source, clips['second'])
        else:
            await send(source, clips[{'dictation':'dictation','interruption':'story','tool':'tool'}[case]])
        events.append({'type':'input_marker', 'name':'phrase_audio_sent', 'elapsed_ms':round((time.monotonic()-start)*1000)})
        await send(source, bytes(48000))
        initial_audio = None
        if case == 'interruption':
            initial_audio = await wait_for(audio.is_set, 70)
            if initial_audio:
                await asyncio.sleep(interrupt_delay)
                events.append({'type':'input_marker', 'name':'interrupt_start', 'elapsed_ms':round((time.monotonic()-start)*1000)})
                await send(source, clips['interrupt'])
                events.append({'type':'input_marker', 'name':'interrupt_audio_sent', 'elapsed_ms':round((time.monotonic()-start)*1000)})
                await send(source, bytes(48000))
                def answered_after_interruption():
                    users = items('transcript', 'user')
                    return len(users) >= 2 and any(x['elapsed_ms'] > users[1]['elapsed_ms'] for x in items('transcript', 'assistant'))
                await wait_for(answered_after_interruption, interrupt_timeout)
        elif case == 'tool':
            await wait_for(lambda: bool(items('tool')) or bool(items('error')), 60)
            await asyncio.sleep(2)
        elif case.startswith('pause'):
            expected = 1 if case == 'pause_short' else 2
            await wait_for(lambda: len(items('transcript', 'user')) >= expected or bool(items('error')), 30)
            await asyncio.sleep(6)
            if case == 'pause_short':
                await wait_for(lambda: audio.is_set() or bool(items('error')), 45)
        else:
            await wait_for(lambda: bool(items('transcript', 'user')) or bool(items('error')), 30)
            await wait_for(lambda: audio.is_set() or bool(items('error')), 45)
            await asyncio.sleep(2)
        turns = [x['text'] for x in items('transcript','user')]
        result = {'case':case, 'user_turns':turns, 'assistant_turns':[x['text'] for x in items('transcript','assistant')], 'events':events}
        marker = next((e['elapsed_ms'] for e in events if e.get('name') == 'phrase_audio_sent'), None)
        user_events = items('transcript', 'user')
        transcript_after_marker = next((e for e in user_events if marker is not None and e['elapsed_ms'] >= marker), None)
        # Long pauses deliberately create two turns, so received audio may be a reply to the first.
        first_audio = next((t for t in audio_times if marker is not None and t >= marker), None) if case != 'pause_long' else None
        result['latency_ms'] = {
            'file_end_to_first_transcript': transcript_after_marker['elapsed_ms'] - marker if transcript_after_marker is not None else None,
            'file_end_to_first_received_audio': first_audio - marker if first_audio is not None else None,
            'provider_metrics': [e['metric'] for e in items('metric')],
        }
        if case == 'dictation': result['wer'] = wer(phrases['dictation'], ' '.join(turns))
        if case.startswith('pause'): result['expected_turns'] = 1 if case == 'pause_short' else 2; result['turns_match'] = len(turns) == result['expected_turns']
        if case == 'tool':
            result['tool_events'] = items('tool')
            result['call_contact_simulated'] = any(x.get('name') == 'call_contact' and 'алексей' in x.get('args',{}).get('name','').lower() for x in items('tool'))
        if case == 'interruption':
            result['initial_audio_received'] = initial_audio
            result['interrupt_metric_received'] = any(x.get('metric',{}).get('type') == 'interrupt' for x in items('metric'))
            result['post_interrupt_user_transcript'] = turns[1:] if len(turns)>1 else []
            result['interrupt_wer'] = wer(phrases['interrupt'], ' '.join(result['post_interrupt_user_transcript']))
            heard = ' '.join(result['post_interrupt_user_transcript']).lower()
            if re.search(r'[a-z]', phrases['interrupt'].lower()):
                result['interrupt_request_preserved'] = ('week' in heard and 'day' in heard)
            else:
                result['interrupt_request_preserved'] = ('недел' in heard and ('дн' in heard or 'ден' in heard)
                                                         and (phrases is not COMPLEX_PHRASES or 'сред' in heard))
            user_events = items('transcript', 'user')
            end = next((e['elapsed_ms'] for e in events if e.get('name') == 'interrupt_audio_sent'), None)
            second_audio = next((t for t in audio_times if len(user_events) >= 2 and t > user_events[1]['elapsed_ms']), None)
            result['latency_ms']['interrupt_file_end_to_transcript'] = user_events[1]['elapsed_ms'] - end if end is not None and len(user_events) >= 2 else None
            result['latency_ms']['interrupt_file_end_to_audio_after_transcript'] = second_audio - end if end is not None and second_audio is not None else None
            result['post_interrupt_assistant_turns'] = (sum(1 for x in items('transcript', 'assistant') if x['elapsed_ms'] > user_events[1]['elapsed_ms']) if len(user_events) >= 2 else 0)
            later = [x['text'] for x in items('transcript', 'assistant') if len(user_events) >= 2 and x['elapsed_ms'] > user_events[1]['elapsed_ms']]
            result['post_interrupt_assistant_text'] = later
            if phrases is COMPLEX_PHRASES:
                answer = ' '.join(later).lower().replace('ё', 'е')
                explicit_sequence = re.search(r'после\s+сред\w*.{0,80}четвер|четвер\w*.{0,80}после\s+сред', answer, re.DOTALL)
                result['post_interrupt_answer_content_checked'] = (bool(re.search(r'\b7\b|\bсем(?:ь|и)\b', answer)) and bool(explicit_sequence)) if later else None
        return result
    finally:
        await room.disconnect()
        for task in readers: task.cancel()
        await client.post(API+'/api/v1/benchmarks/voice/'+info['id']+'/close', headers=headers, json={'metrics':[]})

async def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--fixtures', required=True); parser.add_argument('--generate', action='store_true'); parser.add_argument('--config'); parser.add_argument('--output'); parser.add_argument('--case', choices=('dictation','pause_short','pause_long','interruption','tool')); parser.add_argument('--interrupt-delay', type=float, default=0); parser.add_argument('--interrupt-timeout', type=float, default=70); parser.add_argument('--profile', choices=PROFILES, default='baseline-v1'); parser.add_argument('--fixture-voice', choices=('alloy','nova','onyx'), default='alloy'); args = parser.parse_args()
    path = Path(args.fixtures)
    if args.generate:
        await fixtures(path, PROFILES[args.profile], args.fixture_voice); print('Fixtures ready:', path); return
    if not args.config or not args.output: parser.error('--config and --output are required')
    manifest = json.loads((path/'manifest.json').read_text()); clips = {}
    phrases = PROFILES[args.profile]
    for name in phrases:
        if manifest[name]['text'] != phrases[name]: raise ValueError('Fixture text mismatch: '+name)
        clips[name] = (path/(name+'.pcm')).read_bytes()
        if hashlib.sha256(clips[name]).hexdigest() != manifest[name]['sha256']: raise ValueError('Fixture hash mismatch: '+name)
    config = json.loads(Path(args.config).read_text()); token = sys.stdin.read().strip()
    if not 10 <= args.interrupt_timeout <= 90: parser.error('interrupt timeout must be 10..90 seconds')
    results = {'config':config, 'fixture_set':args.profile, 'fixture_voice':manifest['interrupt'].get('synthetic_voice','alloy'), 'interrupt_delay_seconds':args.interrupt_delay, 'interrupt_timeout_seconds':args.interrupt_timeout, 'fixture_manifest':manifest, 'cases':[], 'limitations':'Synthetic speech; state-based interruption metrics are not acoustic end-to-end latency.'}
    async with httpx.AsyncClient(timeout=30) as client:
        for case in ((args.case,) if args.case else ('dictation','pause_short','pause_long','interruption','tool')):
            print('Running', case, flush=True)
            try: result = await exercise(client, {'Authorization':'Bearer '+token}, config, clips, case, args.interrupt_delay, phrases, args.interrupt_timeout)
            except Exception as exc: result = {'case':case, 'error':type(exc).__name__+': '+str(exc)}
            results['cases'].append(result)
            Path(args.output).write_text(json.dumps(results,ensure_ascii=False,indent=2))
            print('Completed', case, flush=True)

if __name__ == '__main__': asyncio.run(main())
