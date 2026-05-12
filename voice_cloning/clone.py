from __future__ import annotations

import argparse
import os
from pathlib import Path
from pocket_tts import TTSModel
from pocket_tts.models.tts_model import export_model_state
import scipy.io.wavfile

SAMPLE_DIRECTORY = Path(__file__).parent / "sample_voices"
RESULT_DIRECTORY = Path(__file__).parent / "results"
TEST_TEXT = """
Testing voice output in three, two, one.
The rain taps softly against the window while a train rolls through the city at midnight.
A distant announcement echoes across the platform, and somewhere nearby, a coffee machine hums to life.
If every word sounds clear and natural, your text-to-speech setup is working perfectly.
"""

def fetch_sample(filename: str = None) -> Path:
    if filename is None:
        files = SAMPLE_DIRECTORY.glob("*.wav")
        return next(files)
    
    return Path(SAMPLE_DIRECTORY / filename)

def use_clone_voice(file_path: Path, text: str, output_path: Path = None) -> Path:
    tts_model = TTSModel.load_model()
    voice_state = tts_model.get_state_for_audio_prompt(str(file_path))
    audio = tts_model.generate_audio(voice_state, text)
    scipy.io.wavfile.write(str(output_path), tts_model.sample_rate, audio.numpy())

def clone_voice(file_path: Path, text: str) -> Path:
    file_name = file_path.stem
    output_dir = RESULT_DIRECTORY / file_name
    os.makedirs(output_dir, exist_ok=True)
    
    tensors_path = output_dir / "model_state.safetensors"
    wav_path = output_dir / "cloned_voice.wav"

    tts_model = TTSModel.load_model()
    voice_state = tts_model.get_state_for_audio_prompt(str(file_path))
    export_model_state(voice_state, tensors_path)
    
    use_clone_voice(file_path, text, wav_path)

sample = fetch_sample("home_sample.wav")
print(f"Using reference WAV: {sample}")
clone_voice(sample, TEST_TEXT)
print(f"Cloned voice saved to: {RESULT_DIRECTORY / 'cloned_voice.wav'}")