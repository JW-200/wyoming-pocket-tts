from functools import partial
import logging
import socket
import asyncio

from functools import partial
from wyoming.zeroconf import HomeAssistantZeroconf
from wyoming.info import Attribution, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncServer, AsyncTcpServer

from const import (
    PRELOAD_VOICES,
    LOG_LEVEL,
    WYOMING_HOST,
    WYOMING_PORT,
    ZEROCONF_NAME,
    VERSION
)
from utils import ALL_VOICES
from wrapper import PocketTTSWrapper
from wyoming_server import PocketTTSEventHandler
_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=logging.BASIC_FORMAT,
    )

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
    
    hass_zeroconf = HomeAssistantZeroconf(name=ZEROCONF_NAME, port=tcp_server.port, host=zeroconf_host)
    await hass_zeroconf.register_server()
    _LOGGER.debug(f"Zeroconf discovery enabled: name={ZEROCONF_NAME}, port={tcp_server.port}, host={zeroconf_host}")
    _LOGGER.info("Ready")
    _LOGGER.info("Available voices: %s", ", ".join(ALL_VOICES.keys()))
    
    synthesizer = PocketTTSWrapper(preload_model=True, preload_voices=PRELOAD_VOICES)
    await server.run(partial(PocketTTSEventHandler, wyoming_info, synthesizer))
    
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _LOGGER.info("Server stopped")