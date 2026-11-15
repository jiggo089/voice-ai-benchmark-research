"""Streaming Magpie audio through the Riva SynthesizeOnline gRPC protocol."""
from uuid import uuid4
import os
import grpc
from riva.client.proto import riva_tts_pb2, riva_tts_pb2_grpc, riva_audio_pb2
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions, tts


class MagpieStreamingTTS(tts.TTS):
    def __init__(self, voice, endpoint=os.getenv('MAGPIE_GRPC_ENDPOINT', 'localhost:17072')):
        super().__init__(capabilities=tts.TTSCapabilities(streaming=False), sample_rate=22050, num_channels=1)
        self.voice = voice
        self.endpoint = endpoint

    def synthesize(self, text, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS):
        return MagpieChunk(tts=self, input_text=text, conn_options=conn_options)


class MagpieChunk(tts.ChunkedStream):
    async def _run(self, output_emitter: tts.AudioEmitter):
        async with grpc.aio.insecure_channel(self._tts.endpoint) as channel:
            stub = riva_tts_pb2_grpc.RivaSpeechSynthesisStub(channel)
            async def requests():
                yield riva_tts_pb2.SynthesizeSpeechRequest(text=self.input_text, language_code='en-US', voice_name=self._tts.voice, sample_rate_hz=22050, encoding=riva_audio_pb2.LINEAR_PCM)
            output_emitter.initialize(request_id=str(uuid4()), sample_rate=22050, num_channels=1, mime_type='audio/pcm')
            call = stub.SynthesizeOnline(requests(), timeout=120)
            total = 0
            try:
                async for response in call:
                    if response.audio:
                        total += len(response.audio)
                        output_emitter.push(response.audio)
                if not total or total % 2:
                    raise RuntimeError('Magpie returned empty or incomplete audio')
                output_emitter.flush()
            finally:
                call.cancel()
