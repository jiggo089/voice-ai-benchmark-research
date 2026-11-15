"""LiveKit agent that sends each user's audio turn to Nemotron Omni."""
import os
import base64
import io
import math
import struct
import time
import wave
from uuid import uuid4

from livekit.agents import Agent
from openai import AsyncOpenAI

OMNI_TASK_HINT = "Respond directly and naturally to the user's spoken requests."


def trim_leading_silence(pcm: bytes, sample_rate: int = 16000) -> bytes:
    """Drop leading quiet frames, retaining 40 ms of pre-roll before speech.

    This is used only for the model input; the STT stream is unchanged.
    If no audible frame is found, preserve the original audio.
    """
    frame_samples = sample_rate // 100  # 10 ms
    frame_bytes = frame_samples * 2
    for pos in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
        samples = struct.unpack('<' + 'h' * frame_samples, pcm[pos:pos + frame_bytes])
        rms = math.sqrt(sum(s * s for s in samples) / frame_samples)
        if rms >= 45:
            start = max(0, pos - 4 * frame_bytes)
            return pcm[start:]
    return pcm


class OmniAgent(Agent):
    def __init__(self, report, stt, reasoning='auto', temperature=0.7, task_hint=False):
        super().__init__(instructions='')
        self.report = report
        self._audio_stt = stt
        self.reasoning = reasoning
        self.temperature = temperature
        self.task_hint = task_hint

    async def llm_node(self, chat_ctx, tools, model_settings):
        audio = self._audio_stt.last_utterance
        if not audio:
            raise RuntimeError('No completed audio segment for Omni')
        captured_ms = round(len(audio) * 1000 / 32000)
        audio = trim_leading_silence(audio)
        self.report({'type': 'metric', 'metric': {'type': 'omni_audio',
                     'duration_ms': round(len(audio) * 1000 / 32000),
                     'captured_ms': captured_ms}})
        with io.BytesIO() as out:
            with wave.open(out, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(audio)
            data = base64.b64encode(out.getvalue()).decode('ascii')
        messages = []
        for item in chat_ctx.items:
            if getattr(item, 'type', '') != 'message' or item.role not in ('user', 'assistant'):
                continue
            content = ''.join(x for x in item.content if isinstance(x, str))
            if content:
                messages.append({'role': item.role, 'content': content})
        if not messages or messages[-1]['role'] != 'user':
            raise RuntimeError('Missing user turn for Omni')
        messages[-1]['content'] = [{'type':'audio_url', 'audio_url':{'url':'data:audio/wav;base64,' + data}}]
        if self.task_hint:
            messages.insert(0, {'role': 'system', 'content': OMNI_TASK_HINT})
        stream_id = str(uuid4())
        generated = []
        completed = False
        started = time.monotonic()
        first_text = None
        client = AsyncOpenAI(api_key='local', base_url=os.getenv('OMNI_BASE_URL', 'http://localhost:17073/v1'), timeout=120)
        try:
            extra = {} if self.reasoning == 'auto' else {'chat_template_kwargs': {'enable_thinking': self.reasoning == 'on'}}
            response = await client.chat.completions.create(model='nemotron-omni', messages=messages, stream=True, max_tokens=2048, temperature=self.temperature, extra_body=extra)
            async for item in response:
                if not item.choices:
                    continue
                text = item.choices[0].delta.content
                if text:
                    if first_text is None:
                        first_text = time.monotonic()
                    generated.append(text)
                    self.report({'type':'text_delta','stream_id':stream_id,'seq':len(generated)-1,'text':text})
                    yield text
            completed = True
        finally:
            metric = {'type': 'llm', 'duration_ms': round((time.monotonic() - started) * 1000), 'completed': completed}
            if first_text is not None:
                metric['ttft_ms'] = round((first_text - started) * 1000)
            self.report({'type': 'metric', 'metric': metric})
            self.report({'type':'text_delta_end','stream_id':stream_id})
            if generated:
                self.report({'type':'generation','stream_id':stream_id,'text':''.join(generated),'completed':completed})
            await client.close()
