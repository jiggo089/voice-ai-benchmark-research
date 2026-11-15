"""Example English scenario against a compatible LiveKit benchmark API.

Set BENCHMARK_API_URL, supply a configuration JSON and pass a short-lived
benchmark bearer token on stdin. Fixture creation uses OPENAI_API_KEY.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from benchmark_suite import exercise, fixtures

PHRASES = {
    'dictation': 'Please write this down: next Wednesday afternoon I want to call my grandson Alex, ask how his mother is feeling, and then remind Ben to buy bread and milk.',
    'first': 'Could you tell me, if it rains tomorrow and gets colder,',
    'second': 'should I take an umbrella and a warm jacket with me?',
    'story': 'Tell me a long bedtime story about a forest and an exciting adventure.',
    'interrupt': 'Wait, stop the story for now. Instead tell me how many days there are in a week and which day comes after Wednesday.',
}

async def run(args):
    token = sys.stdin.read().strip()
    if not token:
        raise ValueError('Provide a short-lived benchmark token via stdin')
    root = Path(args.fixtures)
    await fixtures(root, PHRASES)
    clips = {k: (root / (k + '.pcm')).read_bytes() for k in PHRASES}
    config = json.loads(Path(args.config).read_text())
    out = {'config': config, 'fixture_set': 'complex-v2-english-adaptation', 'fixture_voice': 'alloy', 'cases': []}
    async with httpx.AsyncClient(timeout=45) as client:
        for case in ('dictation', 'pause_short', 'pause_long', 'interruption'):
            print('Running', case, flush=True)
            result = await exercise(client, {'Authorization': 'Bearer ' + token}, config, clips, case, phrases=PHRASES, interrupt_timeout=90)
            out['cases'].append(result)
            Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print('Results saved to', args.output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixtures', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    asyncio.run(run(parser.parse_args()))
