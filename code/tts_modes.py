"""Explicit buffered playback mode for TTS engines that normally deliver chunks."""
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, tts


class BufferedTTS(tts.TTS):
    def __init__(self, engine):
        super().__init__(capabilities=tts.TTSCapabilities(streaming=False), sample_rate=engine.sample_rate, num_channels=engine.num_channels)
        self._engine = engine

    def synthesize(self, text, *, conn_options=DEFAULT_API_CONNECT_OPTIONS):
        return BufferedChunk(tts=self, input_text=text, conn_options=conn_options)

    async def aclose(self):
        await self._engine.aclose()


class BufferedChunk(tts.ChunkedStream):
    async def _run(self, output_emitter):
        frames = []
        async with self._tts._engine.synthesize(self.input_text, conn_options=self._conn_options) as source:
            async for packet in source:
                frames.append(bytes(packet.frame.data))
        if frames:
            output_emitter.initialize(request_id='buffered', sample_rate=self._tts.sample_rate,
                                      num_channels=self._tts.num_channels, mime_type='audio/pcm')
            for frame in frames:
                output_emitter.push(frame)
            output_emitter.flush()
