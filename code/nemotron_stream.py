"""LiveKit adapter for the NeMo-Speech.cpp realtime transcription protocol."""
import asyncio
import os
import json

import aiohttp
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions, stt


class TurnAudioCapture:
    """Keep short pre-roll while idle, then retain speech until the turn flush."""

    def __init__(self, sample_rate=16000, preroll_seconds=0.8, max_turn_seconds=20):
        self.preroll_bytes = int(sample_rate * 2 * preroll_seconds)
        self.max_turn_bytes = sample_rate * 2 * max_turn_seconds
        self.buffer = bytearray()
        self.speaking = False

    def add(self, pcm: bytes):
        self.buffer.extend(pcm)
        limit = self.max_turn_bytes if self.speaking else self.preroll_bytes
        if len(self.buffer) > limit:
            del self.buffer[:len(self.buffer) - limit]

    def speech_started(self):
        self.speaking = True

    def commit(self) -> bytes:
        audio = bytes(self.buffer)
        self.buffer.clear()
        self.speaking = False
        return audio


class NemotronStreamingSTT(stt.STT):
    def __init__(self, url=os.getenv('NEMOTRON_STT_WS', 'ws://localhost:17070/v1/audio/transcriptions/realtime'), capture_audio=False):
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True, offline_recognize=False, manual_flush=True))
        self.url = url
        self.capture_audio = capture_audio
        self.last_utterance = b''
        self.turn_capture = TurnAudioCapture() if capture_audio else None

    def speech_started(self):
        if self.turn_capture is not None:
            self.turn_capture.speech_started()

    async def _recognize_impl(self, buffer, *, language=None, conn_options):
        raise NotImplementedError('Use the streaming interface')

    def stream(self, *, language=None, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS):
        return NemotronSpeechStream(stt=self, conn_options=conn_options, sample_rate=16000)


class NemotronSpeechStream(stt.SpeechStream):
    async def _run(self):
        async with aiohttp.ClientSession() as client:
            async with client.ws_connect(self._stt.url, heartbeat=20, max_msg_size=2**20) as ws:
                await ws.send_json({'type': 'session.update', 'session': {'sample_rate': 16000, 'language': 'en'}})

                async def send_audio():
                    async for frame in self._input_ch:
                        if isinstance(frame, self._FlushSentinel):
                            if self._stt.turn_capture is not None:
                                captured = self._stt.turn_capture.commit()
                                if captured:
                                    self._stt.last_utterance = captured
                            await ws.send_json({'type': 'input_audio_buffer.commit'})
                        else:
                            pcm = bytes(frame.data)
                            if self._stt.turn_capture is not None:
                                self._stt.turn_capture.add(pcm)
                            await ws.send_bytes(pcm)
                    await ws.send_json({'type': 'input_audio_buffer.commit'})

                async def receive():
                    partial = ''
                    async for message in ws:
                        if message.type == aiohttp.WSMsgType.ERROR:
                            raise RuntimeError('Nemotron websocket failed')
                        if message.type != aiohttp.WSMsgType.TEXT:
                            continue
                        event = json.loads(message.data)
                        kind = event.get('type', '')
                        if kind == 'error':
                            raise RuntimeError('Nemotron ASR error: ' + str(event.get('message', 'unknown')))
                        if kind.endswith('.delta'):
                            partial += event.get('delta', '')
                            if partial:
                                self._event_ch.send_nowait(stt.SpeechEvent(type=stt.SpeechEventType.INTERIM_TRANSCRIPT, alternatives=[stt.SpeechData(language='en', text=partial)]))
                        elif kind.endswith('.completed'):
                            text = event.get('transcript', '')
                            partial = ''
                            if text:
                                self._event_ch.send_nowait(stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[stt.SpeechData(language='en', text=text)]))

                sender = asyncio.create_task(send_audio())
                receiver = asyncio.create_task(receive())
                try:
                    done, _ = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                    if sender in done:
                        await asyncio.wait_for(receiver, timeout=5)
                finally:
                    sender.cancel()
                    receiver.cancel()
                    await asyncio.gather(sender, receiver, return_exceptions=True)
