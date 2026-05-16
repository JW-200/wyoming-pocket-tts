# Voice Cloning

## Steps

1. **Prepare a voice sample**
   - Add a `.wav` file to `sample_voices/`
   - Recommended: 10-30 seconds of clean audio

2. **Run cloning**
    - Install the dependencies if not done already
    - Run python script: `python clone.py`

3. **Find your model**
   - Trained model saved to `results/my_clone/model_state.safetensors`

## File Structure

- `clone.py` - Main cloning script
- `test_voice.py` - Test your cloned voice (text can adopted to your liking)
- `sample_voices/` - Place voice samples here
- `results/` - Cloned models saved here