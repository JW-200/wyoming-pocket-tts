import logging
from pathlib import Path
from wyoming.tts import Synthesize
from const import PREDEFINED_VOICES, VOICE_DIR

_LOGGER = logging.getLogger(__name__)

def discover_custom_voices() -> dict[str, str]:
    """Discover custom voice files (.safetensors) in VOICE_DIR."""
    custom_voices = {}
    
    if not Path(VOICE_DIR).exists():
        return custom_voices
    
    voice_dir = Path(VOICE_DIR)
    for safetensors_file in voice_dir.glob("*.safetensors"):
        voice_name = safetensors_file.stem
        custom_voice_name = f"Custom_{voice_name}"
        custom_voices[custom_voice_name] = str(safetensors_file)
        _LOGGER.info(f"Discovered custom voice: {custom_voice_name} ({safetensors_file})")
    
    return custom_voices

ALL_VOICES = {**PREDEFINED_VOICES, **discover_custom_voices()}

def coerce_voice_name(voice: object | None, default_voice: str) -> str:
    """Normalize a voice value that may be a string, object, or empty."""
    if isinstance(voice, str):
        return voice or default_voice

    if voice and getattr(voice, "name", None):
        return voice.name

    return default_voice

def resolve_voice_name(synthesize: Synthesize, default_voice: str) -> str:
    """Resolve a requested voice name to a known catalog or custom voice key."""
    voice_name = coerce_voice_name(synthesize.voice, default_voice)

    if voice_name in ALL_VOICES:
        return voice_name

    return default_voice