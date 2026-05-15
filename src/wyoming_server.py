import asyncio
import logging
import socket
import time
from functools import partial
from typing import Optional
import threading

from wyoming.zeroconf import HomeAssistantZeroconf
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.event import Event, async_write_event
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler, AsyncServer, AsyncTcpServer
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped
)

from utils import coerce_voice_name, resolve_voice_name, ALL_VOICES
from wrapper import PocketTTSWrapper
from const import (
    DEFAULT_VOICE, LOG_LEVEL, PRELOAD_VOICES, 
    VERSION, WYOMING_HOST, WYOMING_PORT, ZEROCONF,
)

_LOGGER = logging.getLogger(__name__)


class _AsyncWriteAdapter:
    def __init__(self, writer):
        self._writer = writer

    def writelines(self, data):
        self._writer.write(b"".join(data))

    def write(self, data):
        self._writer.write(data)

    async def drain(self):
        await self._writer.drain()

class PocketTTSEventHandler(AsyncEventHandler):
    def __init__(self, wyoming_info, default_voice, tts_handler, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wyoming_info_event = wyoming_info.event()
        self.tts_handler = tts_handler
        self.default_voice = default_voice
        # CRITICAL: Capture the main loop here
        self.loop = asyncio.get_running_loop()
        
        self._text_buffer = ""
        self._audio_started = False
        self._queue = asyncio.Queue()
        self._stream_task = None
        self._stream_voice_name = default_voice
        self._active_mode: Optional[str] = None
        self._active_producers = 0
        self._stream_stopping = False
        self._send_synthesize_stopped = False
        self._producer_lock = threading.Lock()
        self._request_seq = 0
        self._request_id = 0
        self._request_started_ts = 0.0
        self._first_audio_sent_ts = 0.0
        self._audio_chunk_count = 0
        self._audio_bytes_sent = 0

    def _begin_request(self, mode: str, text_len: int = 0, voice_name: Optional[str] = None) -> None:
        self._request_seq += 1
        self._request_id = self._request_seq
        self._request_started_ts = time.perf_counter()
        self._first_audio_sent_ts = 0.0
        self._audio_chunk_count = 0
        self._audio_bytes_sent = 0
        _LOGGER.info(
            "Request %s started mode=%s voice=%s text_len=%s",
            self._request_id,
            mode,
            voice_name or self.default_voice,
            text_len,
        )

    async def handle_event(self, event):
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            return True

        if Synthesize.is_type(event.type):
            synthesize = Synthesize.from_event(event)

            if self._active_mode == "stream":
                _LOGGER.debug("Ignoring legacy synthesize while streaming request is active")
                return True

            voice_name = resolve_voice_name(synthesize, self.default_voice)

            self._active_mode = "single"
            self._stream_stopping = True
            self._send_synthesize_stopped = False
            self._active_producers = 0
            self._begin_request("single", text_len=len(synthesize.text), voice_name=voice_name)
            self._audio_started = False
            self._queue = asyncio.Queue()
            self._stream_task = asyncio.create_task(self._consume_audio_queue())
            if synthesize.text.strip():
                self._start_producer(synthesize.text, voice_name)
            else:
                self._finish_stream_if_ready()
            return True

        if SynthesizeStart.is_type(event.type):
            if self._active_mode == "single":
                _LOGGER.debug("Ignoring streaming synthesize start while single-shot request is active")
                return True

            if self._active_mode == "stream":
                _LOGGER.debug("Ignoring duplicate streaming synthesize start while streaming request is active")
                return True

            stream_start = SynthesizeStart.from_event(event)
            self._active_mode = "stream"
            self._stream_stopping = False
            self._send_synthesize_stopped = True
            self._active_producers = 0
            self._audio_started = False
            self._text_buffer = ""
            self._stream_voice_name = coerce_voice_name(getattr(stream_start, "voice", None), self.default_voice)
            self._begin_request("stream", text_len=0, voice_name=self._stream_voice_name)
            self._queue = asyncio.Queue()
            self._stream_task = asyncio.create_task(self._consume_audio_queue())
            return True

        if SynthesizeChunk.is_type(event.type):
            if self._active_mode != "stream":
                return True

            chunk_text = SynthesizeChunk.from_event(event).text.strip()
            if chunk_text:
                _LOGGER.debug(
                    "Request %s received stream text chunk len=%s",
                    self._request_id,
                    len(chunk_text),
                )
                self._start_producer(chunk_text, self._stream_voice_name)
            return True

        if SynthesizeStop.is_type(event.type):
            if self._active_mode != "stream":
                return True

            self._stream_stopping = True
            self._finish_stream_if_ready()
            return True

        return True

    def _start_producer(self, text: str, voice_name: str) -> None:
        with self._producer_lock:
            self._active_producers += 1

        threading.Thread(
            target=self._produce_audio,
            args=(text, voice_name),
            daemon=True,
        ).start()

    def _finish_stream_if_ready(self) -> None:
        with self._producer_lock:
            ready = self._stream_stopping and self._active_producers == 0

        if ready:
            self.loop.call_soon_threadsafe(self._queue.put_nowait, None)

    def _produce_audio(self, text, voice_name=None):
        """Runs in background thread"""
        try:
            if text:
                selected_voice = voice_name or self.default_voice
                for chunk in self.tts_handler.synthesize(text, selected_voice):
                    # Send raw PCM chunks to the async queue
                    self.loop.call_soon_threadsafe(self._queue.put_nowait, chunk)
        except Exception as e:
            _LOGGER.error(f"Producer error: {e}")
        finally:
            with self._producer_lock:
                self._active_producers = max(0, self._active_producers - 1)

            self._finish_stream_if_ready()

    async def _consume_audio_queue(self):
        """Runs in main thread: Queue -> Socket"""
        rate = self.tts_handler.get_model().sample_rate
        writer = _AsyncWriteAdapter(self.writer)
        try:
            while True:
                chunk = await self._queue.get()
                if chunk is None:
                    break

                if not self._audio_started:
                    await async_write_event(AudioStart(rate, 2, 1).event(), writer)
                    self._audio_started = True

                await async_write_event(AudioChunk(rate, 2, 1, chunk).event(), writer)
                self._audio_chunk_count += 1
                self._audio_bytes_sent += len(chunk)
                if self._first_audio_sent_ts == 0.0:
                    self._first_audio_sent_ts = time.perf_counter()
                    _LOGGER.info(
                        "Request %s first audio sent after %.3fs (%s bytes)",
                        self._request_id,
                        self._first_audio_sent_ts - self._request_started_ts,
                        len(chunk),
                    )

            if self._audio_started:
                await async_write_event(AudioStop().event(), writer)

            if self._send_synthesize_stopped:
                await async_write_event(SynthesizeStopped().event(), writer)
            now = time.perf_counter()
            total_sec = now - self._request_started_ts if self._request_started_ts else 0.0
            first_audio_sec = (
                self._first_audio_sent_ts - self._request_started_ts
                if self._first_audio_sent_ts and self._request_started_ts
                else -1.0
            )
            _LOGGER.info(
                "Request %s finished total=%.3fs first_audio=%.3fs chunks=%s bytes=%s",
                self._request_id,
                total_sec,
                first_audio_sec,
                self._audio_chunk_count,
                self._audio_bytes_sent,
            )
        except (ConnectionResetError, BrokenPipeError, ConnectionError):
            _LOGGER.debug("Client disconnected during audio stream")
        except Exception as e:
            _LOGGER.exception("Consumer error")
        finally:
            self._active_mode = None
            self._send_synthesize_stopped = False


async def main() -> None:
    """Main entry point."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format=logging.BASIC_FORMAT,
    )

    tts_handler = PocketTTSWrapper(preload_model=True, preload_voices=PRELOAD_VOICES)

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