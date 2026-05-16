import os

# Version
VERSION = os.environ.get("VERSION", "Undefined")

# Wyoming Server
WYOMING_HOST = os.environ.get("WYOMING_HOST", "0.0.0.0")
WYOMING_PORT = int(os.environ.get("WYOMING_PORT", "10300"))

# TTS Configuration
DEFAULT_VOICE = os.environ.get("DEFAULT_VOICE", "alba")
VOLUME = float(os.environ.get("VOLUME", "1.0"))
VOICE_DIR = os.environ.get("VOICE_DIR", "/app/custom_voices/")  # Custom voice directory with .safetensors files
PRELOAD_VOICES = [
	voice.strip().strip('"').strip("'")
	for voice in os.environ.get("PRELOAD_VOICES", DEFAULT_VOICE).split(",")
	if voice.strip().strip('"').strip("'")
]

# Features
ZEROCONF_NAME = os.environ.get("ZEROCONF", "pocket-tts")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Predefined voices
PREDEFINED_VOICES = {
    "Alba (en)": "alba",
    "Anna (en)": "anna",
    "Azelma (en)": "azelma",
    "Bill Boerst (en)": "bill_boerst",
    "Caro Davy (en)": "caro_davy",
    "Charles (en)": "charles",
    "Cosette (en)": "cosette",
    "Eponine (en)": "eponine",
    "Eve (en)": "eve",
    "Fantine (en)": "fantine",
    "George (en)": "george",
    "Jane (en)": "jane",
    "Javert (en)": "javert",
    "Jean (en)": "jean",
	"Marius (en)": "marius",
    "Mary (en)": "mary",
    "Michael (en)": "michael",
    "Paul (en)": "paul",
    "Peter Yearsley (en)": "peter_yearsley",
    "Stuart Bell (en)": "stuart_bell",
    "Vera (en)": "vera",
    "Giovanni (it)": "giovanni",
    "Lola (es)": "lola",
    "Juergen (de)": "juergen",
    "Rafael (pt)": "rafael",
    "Estelle (fr)": "estelle"
}