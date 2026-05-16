# Wyoming Pocket-TTS

Simple Wyoming TTS server using Pocket-TTS.

## Steps

1. **Run container**
    - Run:
        `docker run --rm -p 10300:10300 -e DEFAULT_VOICE=alba -e LOG_LEVEL=INFO ghcr.io/jw-200/wyoming-pocket-tts:0.0.1`

2. **Use custom voices (optional)**
    - Put `.safetensors` files in a local folder (example: `./custom_voices`)
    - Run with volume mount:
        `docker run --rm -p 10300:10300 -e VOICE_DIR=/app/custom_voices -v ${PWD}/custom_voices:/app/custom_voices ghcr.io/jw-200/wyoming-pocket-tts:0.0.1`
    - Voice name format is: `custom_<file_name_without_extension>`

3. **Connect from Home Assistant**
    - Add Wyoming integration
    - Host: your Docker host IP
    - Port: `10300`

## Environment Variables

- `WYOMING_HOST` (default: `0.0.0.0`) - Bind address inside the container.
- `WYOMING_PORT` (default: `10300`) - Wyoming TCP port to expose.
- `DEFAULT_VOICE` (default: `alba`) - Voice used when the client does not request one.
- `VOICE_DIR` (default: `/app/custom_voices/`) - Folder scanned for custom `.safetensors` voices.
- `PRELOAD_VOICES` (default: same as `DEFAULT_VOICE`) - Comma-separated voice names to preload at startup.
- `VOLUME` (default: `1.0`) - Output gain multiplier.
- `LOG_LEVEL` (default: `INFO`) - Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- `ZEROCONF` (default: `pocket-tts`) - Zeroconf service name shown to Home Assistant discovery.