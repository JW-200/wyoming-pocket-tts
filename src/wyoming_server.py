import asyncio
import logging
import time
from typing import Optional
import threading

from sentence_stream  import SentenceBoundaryDetector
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import async_write_event
from wyoming.error import Error
from wyoming.info import Describe
from wyoming.server import AsyncEventHandler
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped
)

from utils import coerce_voice_name, resolve_voice_name
from wrapper import PocketTTSWrapper
from const import PRELOAD_VOICES, DEFAULT_VOICE

_LOGGER = logging.getLogger(__name__)

class PocketTTSEventHandler(AsyncEventHandler):
    def __init__(self, wyoming_info, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wyoming_info_event = wyoming_info.event()
        self._is_streaming: Optional[bool] = None
        self._synthesize: Optional[Synthesize] = None
        self._sbd = SentenceBoundaryDetector()
        self._synthesizer = PocketTTSWrapper(preload_model=True, preload_voices=PRELOAD_VOICES)

    async def handle_event(self, event):
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent info")
            return True
        
        try:
            if Synthesize.is_type(event.type):
                if self._is_streaming:
                    # Ignore since this is only sent for compatibility reasons.
                    # For streaming, we expect:
                    # [synthesize-start] -> [synthesize-chunk]+ -> [synthesize]? -> [synthesize-stop]
                    return True

                # Sent outside a stream, so we must process it
                synthesize = Synthesize.from_event(event)
                self._synthesize = Synthesize(text="", voice=synthesize.voice)
                start_sent = False
                for i, sentence in enumerate(self._sbd.add_chunk(synthesize.text)):
                    self._synthesize.text = sentence
                    await self._handle_synthesize(self._synthesize, send_start=(i == 0), send_stop=False)
                    start_sent = True

                self._synthesize.text = self._sbd.finish()
                if self._synthesize.text:
                    # Last sentence
                    await self._handle_synthesize(self._synthesize, send_start=(not start_sent), send_stop=True)
                else:
                    # No final sentence
                    await self.write_event(AudioStop().event())

                return True

            if SynthesizeStart.is_type(event.type):
                # Start of a stream
                stream_start = SynthesizeStart.from_event(event)
                self._is_streaming = True
                self._sbd = SentenceBoundaryDetector()
                self._synthesize = Synthesize(text="", voice=stream_start.voice)
                _LOGGER.debug("Text stream started: voice=%s", stream_start.voice)
                return True

            if SynthesizeChunk.is_type(event.type):
                assert self._synthesize is not None
                stream_chunk = SynthesizeChunk.from_event(event)
                for sentence in self._sbd.add_chunk(stream_chunk.text):
                    _LOGGER.debug("Synthesizing stream sentence: %s", sentence)
                    self._synthesize.text = sentence
                    await self._handle_synthesize(self._synthesize)

                return True

            if SynthesizeStop.is_type(event.type):
                assert self._synthesize is not None
                self._synthesize.text = self._sbd.finish()
                if self._synthesize.text:
                    # Final audio chunk(s)
                    await self._handle_synthesize(self._synthesize)

                # End of audio
                await self.write_event(SynthesizeStopped().event())

                _LOGGER.debug("Text stream stopped")
                return True

            if not Synthesize.is_type(event.type):
                return True

            synthesize = Synthesize.from_event(event)
            return await self._handle_synthesize(synthesize)
        except Exception as err:
            await self.write_event(Error(text=str(err), code=err.__class__.__name__).event())
            raise err
        
    async def _handle_synthesize(self, synthesize: Synthesize, send_start=True, send_stop=True):
        voice_name = resolve_voice_name(synthesize, DEFAULT_VOICE)
        _LOGGER.debug("Synthesizing text len=%s with voice=%s", len(synthesize.text), voice_name)
        for chunk in self._synthesizer.synthesize(synthesize.text, voice_name):
            if send_start:
                await self.write_event(AudioStart(self._synthesizer.get_model().sample_rate, 2, 1).event())
                send_start = False

            await self.write_event(AudioChunk(self._synthesizer.get_model().sample_rate, 2, 1, chunk).event())

        if not send_start:
            await self.write_event(AudioStart(self._synthesizer.get_model().sample_rate, 2, 1).event())

        if send_stop:
            await self.write_event(AudioStop().event())