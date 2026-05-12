from pocket_tts import TTSModel
import scipy.io.wavfile
from pathlib import Path

RESULT_DIRECTORY = Path(__file__).parent / "results"
TEST_TEXT = """
Smart home assistant online and fully caffeinated.
Good morning! I have opened the blinds, started warming the kitchen lights, and detected exactly one human pretending not to be awake yet.
The robot vacuum has escaped its docking station and is now exploring the hallway with great confidence.
Your fridge would also like to remind you that buying vegetables was an optimistic decision.
Meanwhile, rain clouds are approaching, the coffee machine is ready for duty, and your favorite playlist is standing by.
"""

def generate_audio(dir_name: Path, text: str) -> Path:
    tensor_path = RESULT_DIRECTORY / dir_name / "model_state.safetensors"
    output_path = RESULT_DIRECTORY / dir_name / "test_audio.wav"
    
    tts_model = TTSModel.load_model()
    voice_state = tts_model.get_state_for_audio_prompt(str(tensor_path))
    audio = tts_model.generate_audio(voice_state, text)
    scipy.io.wavfile.write(str(output_path), tts_model.sample_rate, audio.numpy())
    

for dirs in RESULT_DIRECTORY.iterdir():
    if dirs.is_dir():
        generate_audio(dirs, TEST_TEXT)