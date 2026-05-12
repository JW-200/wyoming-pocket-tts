"""PocketTTS model wrapper - handles all model-related operations."""

import asyncio
import logging
import queue
import threading
from typing import AsyncGenerator, Optional
import numpy
from pocket_tts import TTSModel
from const import (
    DEFAULT_VOICE,
    PRELOAD_VOICES,
    STREAM_CHUNK_SIZE,
    VOLUME,
)
from utils import ALL_VOICES

_LOGGER = logging.getLogger(__name__)

class PocketTTS:
    """Wrapper for Pocket-TTS model with voice state management."""
    def __init__(self) -> None:
        """Initialize the model wrapper."""
        self.model: Optional[TTSModel] = None
        self._voice_states: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        """Load the TTS model and pre-load all voice states."""
        _LOGGER.info("Loading Pocket-TTS model...")
        self.model = TTSModel.load_model()
        
        _LOGGER.info("Model loaded successfully")
        _LOGGER.info(f"Sample rate: {self.sample_rate} Hz")

        preload_voices = list(dict.fromkeys([DEFAULT_VOICE, *PRELOAD_VOICES]))
        _LOGGER.info(f"Pre-loading voice states for {len(preload_voices)} voices...")
        for voice_name in preload_voices:
            try:
                if voice_name not in ALL_VOICES:
                    _LOGGER.warning(f"Skipping unknown preload voice: {voice_name}")
                    continue

                prompt = ALL_VOICES.get(voice_name, DEFAULT_VOICE)
                voice_state = self.model.get_state_for_audio_prompt(prompt)
                self._voice_states[voice_name] = voice_state
                _LOGGER.info(f"Loaded voice state for: {voice_name}")
            except Exception as e:
                _LOGGER.debug(f"Could not pre-load voice '{voice_name}': {e}")
        _LOGGER.info("Voice states pre-loaded")

    @property
    def sample_rate(self) -> int:
        """Get sample rate of the model."""
        return self.model.sample_rate

    async def get_voice_state(self, voice_name: str) -> dict:
        """Get or load voice state for given voice."""
        async with self._lock:
            if voice_name not in self._voice_states:
                _LOGGER.info(f"Loading voice state for: {voice_name}")
                try:
                    prompt = ALL_VOICES.get(voice_name, DEFAULT_VOICE)
                    self._voice_states[voice_name] = self.model.get_state_for_audio_prompt(prompt)
                except Exception as e:
                    _LOGGER.error(f"Failed to load voice state for {voice_name}: {e}")
                    raise

            return self._voice_states[voice_name]

    async def synthesize(self, text: str, voice_name: str) -> AsyncGenerator[bytes, None]:
        """Synthesize audio for given text and voice as an async stream."""
        if not text:
            _LOGGER.warning("Empty text received")
            return

        if voice_name not in self._voice_states:
            if voice_name not in ALL_VOICES:
                _LOGGER.warning(f"Voice '{voice_name}' not found in available voices")
            
            try:
                voice_state = await self.get_voice_state(voice_name)
            except Exception as e:
                _LOGGER.error(f"Failed to synthesize with voice '{voice_name}': {e}")
                raise ValueError(f"Voice '{voice_name}' not available: {e}")
        else:
            voice_state = self._voice_states[voice_name]

        try:
            _LOGGER.info(f"Synthesizing text (voice: {voice_name}, length: {len(text)} chars)")
            audio_queue: queue.Queue[object] = queue.Queue(maxsize=32)
            sentinel = object()

            def _synthesis_worker() -> None:
                try:
                    produced_audio = False

                    for audio_chunk in self.model.generate_audio_stream(
                        model_state=voice_state, text_to_generate=text
                    ):
                        produced_audio = True
                        audio_array = audio_chunk.detach().cpu().numpy() * VOLUME
                        audio_bytes = (
                            audio_array.clip(-1.0, 1.0) * 32767
                        ).astype("int16").tobytes()

                        if not audio_bytes:
                            continue

                        chunk_size = STREAM_CHUNK_SIZE * 2
                        for offset in range(0, len(audio_bytes), chunk_size):
                            chunk = audio_bytes[offset : offset + chunk_size]
                            if chunk:
                                audio_queue.put(chunk)

                    if not produced_audio:
                        _LOGGER.warning("No audio generated")
                except Exception as worker_error:
                    audio_queue.put(worker_error)
                finally:
                    audio_queue.put(sentinel)

            worker = threading.Thread(target=_synthesis_worker, daemon=True)
            worker.start()

            while True:
                item = await asyncio.to_thread(audio_queue.get)
                if item is sentinel:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item

        except Exception as e:
            _LOGGER.error(f"Error during synthesis: {e}", exc_info=True)
            raise
