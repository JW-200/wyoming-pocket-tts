import os

# Version
VERSION = os.environ.get("VERSION", "Undefined")

# Wyoming Server
WYOMING_HOST = os.environ.get("WYOMING_HOST", "0.0.0.0")
WYOMING_PORT = int(os.environ.get("WYOMING_PORT", "10300"))

# TTS Configuration
DEFAULT_VOICE = os.environ.get("DEFAULT_VOICE", "Alba (en)")
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
    "(Predefined) Alba (en)": "alba",
    "(Predefined) Anna (en)": "anna",
    "(Predefined) Azelma (en)": "azelma",
    "(Predefined) Bill Boerst (en)": "bill_boerst",
    "(Predefined) Caro Davy (en)": "caro_davy",
    "(Predefined) Charles (en)": "charles",
    "(Predefined) Cosette (en)": "cosette",
    "(Predefined) Eponine (en)": "eponine",
    "(Predefined) Eve (en)": "eve",
    "(Predefined) Fantine (en)": "fantine",
    "(Predefined) George (en)": "george",
    "(Predefined) Jane (en)": "jane",
    "(Predefined) Javert (en)": "javert",
    "(Predefined) Jean (en)": "jean",
	"(Predefined) Marius (en)": "marius",
    "(Predefined) Mary (en)": "mary",
    "(Predefined) Michael (en)": "michael",
    "(Predefined) Paul (en)": "paul",
    "(Predefined) Peter Yearsley (en)": "peter_yearsley",
    "(Predefined) Stuart Bell (en)": "stuart_bell",
    "(Predefined) Vera (en)": "vera",
    "(Predefined) Giovanni (it)": "giovanni",
    "(Predefined) Lola (es)": "lola",
    "(Predefined) Juergen (de)": "juergen",
    "(Predefined) Rafael (pt)": "rafael",
    "(Predefined) Estelle (fr)": "estelle"
}