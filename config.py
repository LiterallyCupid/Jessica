from pathlib import Path

# ==========================================================
# Paths
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

ENV_FILE = BASE_DIR / ".env"

AIMP_EXE = r"C:\Program Files\AIMP\AIMP.exe"

TRACK_PATH = (
    r"C:\Music\OST\Ala Vaikunthapurramuloo - OST (2023)"
    r"\02. Thaman S - Bantu Intro.flac"
)

# ==========================================================
# Audio
# ==========================================================

SAMPLE_RATE = 44100
BLOCK_MS = 40
CHANNELS = 1

INPUT_PROBE_S = 0.5
INPUT_SILENT_RMS = 0.001

# ==========================================================
# Clap Detection
# ==========================================================

SPIKE_RATIO = 7.0

MIN_RMS = 0.012

COOLDOWN_S = 0.45

MIN_DOUBLE_GAP_S = 0.05
MAX_DOUBLE_GAP_S = 0.35

RETRIGGER_RATIO = 0.55

NOISE_FLOOR_ALPHA = 0.992

QUIET_GATE_MULT = 2.2

# ==========================================================
# Welcome
# ==========================================================

WELCOME_ENABLED = True

AFTER_SONG_DELAY_S = 1.0

WELCOME_CACHE_ENABLED = False

# ==========================================================
# Browser
# ==========================================================

OPEN_CHATGPT = True

OPEN_TRADINGVIEW = True

OPEN_BRAVE_FULLSCREEN = True

BRAVE_SEPARATE_SITE_PROFILES = False

CHATGPT_BRAVE_MONITOR = 1

TRADINGVIEW_BRAVE_MONITOR = 2

# ==========================================================
# ElevenLabs
# ==========================================================

DEFAULT_MODEL = "eleven_multilingual_v2"

DEFAULT_OUTPUT_FORMAT = "pcm_24000"

DEFAULT_PCM_RATE = 24000

# ==========================================================
# Jessica
# ==========================================================

JESSICA_CLOSINGS = [
    "Ready when you are.",
    "All systems are operational.",
    "Your workspace is prepared.",
    "I've got everything ready.",
    "Let's build something today.",
]

# ==========================================================
# OpenWeather
# ==========================================================

WEATHER_CACHE_SECONDS = 600