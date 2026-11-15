"""NeuralDeep sentence-level TTS adapter, validating engine and actual WAV bytes."""
import io
import logging
import os
import wave
from uuid import uuid4

import httpx
from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    APIConnectOptions,
    APIStatusError,
    tts,
)

log = logging.getLogger("voice_benchmark.neuraldeep")
NEURALDEEP_TTS_URL = "https://api.neuraldeep.ru/v1/audio/speech"


class NeuralDeepTTS(tts.TTS):
    def __init__(self, *, model: str, voice: str, language: str, stream_audio: bool = False):
        super().__init__(capabilities=tts.TTSCapabilities(streaming=False), sample_rate=24000, num_channels=1)
        if stream_audio and model != "qwen3-tts":
            raise ValueError("streaming is not verified for this NeuralDeep model")
        self._stream_audio = stream_audio
        self._nd_model = model
        self._nd_voice = voice
        self._nd_language = {"ru": "Russian", "en": "English"}[language]

    def synthesize(self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS):
        return NeuralDeepChunk(tts=self, input_text=text, conn_options=conn_options)


class NeuralDeepChunk(tts.ChunkedStream):
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        engine = self._tts
        if engine._stream_audio:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
                async with client.stream('POST', NEURALDEEP_TTS_URL,
                        headers={'Authorization': 'Bearer ' + os.environ['NEURALDEEP_API_KEY']},
                        json={'model': engine._nd_model, 'voice': engine._nd_voice,
                              'language': engine._nd_language, 'input': self.input_text,
                              'response_format': 'pcm', 'stream': True}) as response:
                    if response.status_code != 200:
                        raise APIStatusError('NeuralDeep TTS failed', status_code=response.status_code, retryable=False)
                    if response.headers.get('x-tts-engine', '').casefold() != 'qwen':
                        raise APIStatusError('NeuralDeep TTS returned a different or unknown engine', retryable=False)
                    if response.headers.get('content-type', '').split(';')[0].strip().casefold() != 'audio/pcm':
                        raise APIStatusError('NeuralDeep TTS returned a non-PCM stream', retryable=False)
                    output_emitter.initialize(request_id=response.headers.get('x-request-id') or str(uuid4()),
                                              sample_rate=24000, num_channels=1, mime_type='audio/pcm')
                    total = 0
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            total += len(chunk)
                            output_emitter.push(chunk)
                    if not total or total % 2:
                        raise APIStatusError('NeuralDeep TTS returned incomplete PCM', retryable=False)
                    output_emitter.flush()
            return
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
            response = await client.post(
                NEURALDEEP_TTS_URL,
                headers={"Authorization": "Bearer " + os.environ["NEURALDEEP_API_KEY"]},
                json={"model": engine._nd_model, "voice": engine._nd_voice, "language": engine._nd_language,
                      "input": self.input_text},
            )
        if response.status_code != 200:
            raise APIStatusError("NeuralDeep TTS failed", status_code=response.status_code, retryable=False)
        actual = response.headers.get("x-tts-engine", "").casefold()
        expected = {"qwen3-tts": "qwen", "espeech-tts": "espeech"}[engine._nd_model]
        if actual != expected:
            raise APIStatusError("NeuralDeep TTS returned a different or unknown engine", retryable=False)
        try:
            with wave.open(io.BytesIO(response.content), "rb") as audio:
                if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth(), audio.getcomptype()) != (24000, 1, 2, "NONE"):
                    raise ValueError("unsupported WAV format")
                pcm = audio.readframes(audio.getnframes())
        except (wave.Error, EOFError, ValueError) as exc:
            raise APIStatusError("NeuralDeep TTS returned an invalid WAV", retryable=False) from exc
        if not pcm:
            raise APIStatusError("NeuralDeep TTS returned empty audio", retryable=False)
        log.info("neuraldeep_tts engine=%s bytes=%d", actual, len(pcm))
        output_emitter.initialize(request_id=response.headers.get("x-request-id") or str(uuid4()), sample_rate=24000,
                                  num_channels=1, mime_type="audio/pcm")
        output_emitter.push(pcm)
        output_emitter.flush()
