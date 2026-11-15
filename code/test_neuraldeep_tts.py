"""Offline validation for NeuralDeep's WAV and engine selection contract."""
import io
import os
import unittest
import wave
from unittest.mock import patch

import httpx
from livekit.agents import APIConnectOptions, APIStatusError
from neuraldeep_tts import NeuralDeepTTS


def wav():
    out = io.BytesIO()
    with wave.open(out, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\x01\x00" * 4800)
    return out.getvalue()


class TTSContract(unittest.IsolatedAsyncioTestCase):
    async def run_engine(self, *, reported, content, content_type="audio/mpeg"):
        async def handler(request):
            assert request.url.host == "api.neuraldeep.ru"
            return httpx.Response(200, headers={"x-tts-engine": reported, "content-type": content_type}, content=content)

        real_client = httpx.AsyncClient
        with patch.dict(os.environ, {"NEURALDEEP_API_KEY": "test-only"}), patch(
            "neuraldeep_tts.httpx.AsyncClient", side_effect=lambda **_: real_client(transport=httpx.MockTransport(handler))
        ):
            engine = NeuralDeepTTS(model="espeech-tts", voice="serena", language="ru")
            try:
                return [part async for part in engine.synthesize("test", conn_options=APIConnectOptions(max_retry=0))]
            finally:
                await engine.aclose()

    async def test_uses_actual_wav_when_content_type_is_wrong(self):
        frames = await self.run_engine(reported="espeech", content=wav())
        self.assertTrue(frames)
        self.assertTrue(all(f.frame.sample_rate == 24000 for f in frames))

    async def test_rejects_unexpected_engine(self):
        with self.assertRaises(APIStatusError):
            await self.run_engine(reported="qwen", content=wav())

    async def test_rejects_invalid_audio(self):
        with self.assertRaises(APIStatusError):
            await self.run_engine(reported="espeech", content=b"invalid")


if __name__ == "__main__":
    unittest.main()
