import logging
from typing import Generator, Optional
from pocket_tts import TTSModel

from utils import ALL_VOICES
from const import (
    DEFAULT_VOICE,
    VOLUME
)

_LOGGER = logging.getLogger(__name__)

class PocketTTSWrapper:
    def __init__(self, preload_model: bool, preload_voices: list) -> None:
        self._model: Optional[TTSModel] = None
        self._voice_states: dict[str, dict] = {}
        
        if preload_model:
            self._preload_model()

        if preload_voices:
            self._preload_voice_states(preload_voices)
        
    def _preload_model(self) -> None:
        """Load the TTS model and pre-load specified voice states."""
        self._model = TTSModel.load_model()

    def _preload_voice_states(self, voices: list) -> None:
        """Pre-load voice states for a list of voices."""
        for voice_name in voices:
            if voice_name not in ALL_VOICES:
                raise ValueError(f"Unknown voice for pre-loading: {voice_name}")

            prompt = ALL_VOICES.get(voice_name, DEFAULT_VOICE)
            self._voice_states[voice_name] = self._model.get_state_for_audio_prompt(prompt)

    def get_model(self) -> TTSModel:
        """Get the loaded TTS model, loading it if necessary."""
        if self._model is None:
            self._preload_model()
        return self._model
    
    def get_voice_state(self, voice_name: str) -> dict:
        """Get or load voice state for given voice."""
        if voice_name not in self._voice_states:
            prompt = ALL_VOICES.get(voice_name, DEFAULT_VOICE)
            self._voice_states[voice_name] = self.get_model().get_state_for_audio_prompt(prompt)

        return self._voice_states[voice_name]
    
    def synthesize(self, text: str, voice_name: str) -> Generator[bytes, None, None]:
        """Synthesize audio for given text and voice as a generator."""
        voice_state = self.get_voice_state(voice_name)
        try:

            for audio_chunk in self.get_model().generate_audio_stream(voice_state, text):
                audio_array = audio_chunk.detach().cpu().numpy().flatten() * VOLUME
                audio_bytes = (audio_array.clip(-1.0, 1.0) * 32767).astype("int16").tobytes()
                yield audio_bytes
        except Exception as e:
            _LOGGER.error(f"Error during synthesis: {e}", exc_info=True)