import asyncio
import logging
from functools import partial
from typing import Optional
from const import (
    DEFAULT_VOICE,
    LOG_LEVEL,
    VERSION,
    WYOMING_HOST,
    WYOMING_PORT,
    ZEROCONF,
)
from wyoming.zeroconf import HomeAssistantZeroconf
import socket
from pocket_tts_wrapper import ALL_VOICES, PocketTTS
from utils import resolve_voice_name
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler, AsyncServer, AsyncTcpServer
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped,
)

_LOGGER = logging.getLogger(__name__)

class PocketTTSEventHandler(AsyncEventHandler):
    """Event handler for Pocket-TTS Wyoming server."""
    def __init__(self, wyoming_info: Info, default_voice: str, tts_handler: PocketTTS, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.wyoming_info_event = wyoming_info.event()
        self.default_voice = default_voice
        self.tts_handler = tts_handler
        self.is_streaming: Optional[bool] = None
        self._synthesize: Optional[Synthesize] = None
        self._stream_text: str = ""

    async def handle_event(self, event: Event) -> bool:
        """Handle incoming Wyoming protocol events."""
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent info")
            return True

        try:
            if Synthesize.is_type(event.type):
                if self.is_streaming:
                    return True

                synthesize = Synthesize.from_event(event)
                await self._handle_synthesize(synthesize, send_start=True, send_stop=True)
                return True

            if SynthesizeStart.is_type(event.type):
                stream_start = SynthesizeStart.from_event(event)
                self.is_streaming = True
                self._stream_text = ""
                self._synthesize = Synthesize(text="", voice=stream_start.voice)
                _LOGGER.debug("Text stream started: voice=%s", stream_start.voice)
                return True

            if SynthesizeChunk.is_type(event.type):
                assert self._synthesize is not None
                stream_chunk = SynthesizeChunk.from_event(event)
                self._stream_text += stream_chunk.text
                _LOGGER.debug("Received stream chunk: %s", stream_chunk.text[:50])
                return True

            if SynthesizeStop.is_type(event.type):
                assert self._synthesize is not None
                if self._stream_text.strip():
                    self._synthesize.text = self._stream_text.strip()
                    await self._handle_synthesize(
                        self._synthesize, send_start=True, send_stop=True
                    )

                await self.write_event(SynthesizeStopped().event())
                self.is_streaming = False
                self._stream_text = ""
                _LOGGER.debug("Text stream stopped")
                return True

            return True
        except Exception as err:
            await self.write_event(
                Error(text=str(err), code=err.__class__.__name__).event()
            )
            raise err

    async def _handle_synthesize(self, synthesize: Synthesize, send_start: bool = True, send_stop: bool = True) -> bool:
        """Handle synthesis request."""
        _LOGGER.debug(synthesize)

        raw_text = synthesize.text

        if not raw_text.strip():
            _LOGGER.warning("Empty text received")
            if send_stop:
                await self.write_event(AudioStop().event())
            return True

        voice_name = resolve_voice_name(synthesize, self.default_voice)

        try:
            sample_rate = self.tts_handler.sample_rate
            width = 2
            channels = 1

            if send_start:
                await self.write_event(AudioStart(sample_rate, width, channels).event())

            chunk_count = 0
            _LOGGER.info("Synthesizing text for voice: %s", voice_name)

            async for chunk in self.tts_handler.synthesize(raw_text, voice_name):
                if not chunk:
                    continue

                chunk_count += 1

                await self.write_event(AudioChunk(sample_rate, width, channels, chunk).event())

            if send_stop:
                await self.write_event(AudioStop().event())

            if chunk_count > 0:
                _LOGGER.info("Synthesis complete (%d chunks)", chunk_count)
            else:
                _LOGGER.warning("No audio chunks generated")
        except Exception as e:
            _LOGGER.error("Error during synthesis: %s", e, exc_info=True)
            await self.write_event(Error(text=str(e), code=e.__class__.__name__).event())
        finally:
            return True

async def main() -> None:
    """Main entry point."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=logging.BASIC_FORMAT,
    )

    tts_handler = PocketTTS()
    await tts_handler.load()

    voices = [
        TtsVoice(
            name=voice_name,
            description=f"Pocket-TTS voice: {voice_name}",
            attribution=Attribution(
                name="Kyutai Pocket-TTS",
                url="https://github.com/kyutai-labs/pocket-tts",
            ),
            installed=True,
            version=None,
            languages=["en"],
            speakers=None,
        )
        for voice_name in sorted(ALL_VOICES.keys())
    ]

    wyoming_info = Info(
        tts=[
            TtsProgram(
                name="pocket-tts",
                description="A fast, local, neural text to speech engine",
                attribution=Attribution(
                    name="Kyutai Pocket-TTS",
                    url="https://github.com/kyutai-labs/pocket-tts",
                ),
                installed=True,
                voices=sorted(voices, key=lambda v: v.name),
                version=VERSION,
                supports_synthesize_streaming=True,
            )
        ],
    )

    server_uri = f"tcp://{WYOMING_HOST}:{WYOMING_PORT}"

    server = AsyncServer.from_uri(server_uri)
    
    tcp_server: AsyncTcpServer = server
    zeroconf_host = tcp_server.host
    if zeroconf_host == "0.0.0.0" or not zeroconf_host:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            zeroconf_host = s.getsockname()[0]
            s.close()
        except Exception:
            zeroconf_host = "127.0.0.1"
    
    hass_zeroconf = HomeAssistantZeroconf(name=ZEROCONF, port=tcp_server.port, host=zeroconf_host)
    await hass_zeroconf.register_server()
    _LOGGER.debug(f"Zeroconf discovery enabled: name={ZEROCONF}, port={tcp_server.port}, host={zeroconf_host}")
    _LOGGER.info("Ready")
    _LOGGER.info("Available voices: %s", ", ".join(ALL_VOICES.keys()))
    await server.run(partial(PocketTTSEventHandler, wyoming_info, DEFAULT_VOICE, tts_handler))
    
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _LOGGER.info("Server stopped")