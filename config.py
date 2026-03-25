import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional in minimal test environments
    def load_dotenv():
        return False

load_dotenv()


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_TRANSCRIBE_MODEL = os.environ.get(
    "OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"
)
OPENAI_TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts-2025-12-15")
OPENAI_TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE", "coral")
OPENAI_TTS_SPEED = float(os.environ.get("OPENAI_TTS_SPEED", "1.1"))  # 0.25–4.0
OPENAI_TTS_GAIN_DB = float(os.environ.get("OPENAI_TTS_GAIN_DB", "9"))  # extra dB boost (e.g. 9 ≈ 2.8× louder)
OPENAI_TTS_INSTRUCTIONS = os.environ.get(
    "OPENAI_TTS_INSTRUCTIONS",
    "Speak in a warm, sweet, and playful tone with a gentle high pitch. "
    "Sound like an adorable, tiny friend who is genuinely excited to help. "
    "Use natural breathing and smooth pacing — never robotic or monotone. "
    "Let sentences flow into each other without awkward pauses.",
)

OPENCLAW_BASE_URL = os.environ.get("OPENCLAW_BASE_URL", "http://localhost:18789")
OPENCLAW_TOKEN = os.environ.get("OPENCLAW_TOKEN", "")
TRANSCRIBE_BASE_URL = os.environ.get("TRANSCRIBE_BASE_URL", OPENCLAW_BASE_URL)
TRANSCRIBE_API_TOKEN = os.environ.get(
    "TRANSCRIBE_API_TOKEN", OPENCLAW_TOKEN or OPENAI_API_KEY
)
TRANSCRIBE_HTTP_PATH = os.environ.get(
    "TRANSCRIBE_HTTP_PATH", "/v1/audio/transcriptions"
)
TRANSCRIBE_LANGUAGE = os.environ.get("TRANSCRIBE_LANGUAGE", "").strip()
STT_MODE = os.environ.get("STT_MODE", "oneshot").strip().lower() or "oneshot"
REALTIME_STT_BASE_URL = os.environ.get("REALTIME_STT_BASE_URL", OPENCLAW_BASE_URL)
REALTIME_STT_API_TOKEN = os.environ.get(
    "REALTIME_STT_API_TOKEN", OPENCLAW_TOKEN or TRANSCRIBE_API_TOKEN
)
REALTIME_STT_HTTP_PATH = os.environ.get(
    "REALTIME_STT_HTTP_PATH", "/plugins/macos-say-tts/asr/realtime"
)
REALTIME_STT_LANGUAGE = os.environ.get("REALTIME_STT_LANGUAGE", TRANSCRIBE_LANGUAGE).strip()
REALTIME_STT_CHUNK_MS = int(os.environ.get("REALTIME_STT_CHUNK_MS", "100"))
REALTIME_STT_CONNECT_TIMEOUT_SECONDS = float(
    os.environ.get("REALTIME_STT_CONNECT_TIMEOUT_SECONDS", "10")
)
REALTIME_STT_COMMIT_TIMEOUT_SECONDS = float(
    os.environ.get("REALTIME_STT_COMMIT_TIMEOUT_SECONDS", "8")
)
REALTIME_STT_SHOW_PARTIAL = os.environ.get(
    "REALTIME_STT_SHOW_PARTIAL", "true"
).lower() in ("true", "1", "yes")
REALTIME_STT_FALLBACK_TO_ONESHOT = os.environ.get(
    "REALTIME_STT_FALLBACK_TO_ONESHOT", "true"
).lower() in ("true", "1", "yes")
TTS_BASE_URL = os.environ.get("TTS_BASE_URL", OPENCLAW_BASE_URL)
TTS_API_TOKEN = os.environ.get("TTS_API_TOKEN", OPENCLAW_TOKEN or OPENAI_API_KEY)
TTS_HTTP_PATH = os.environ.get("TTS_HTTP_PATH", "/v1/audio/speech")

AUDIO_DEVICE = os.environ.get("AUDIO_DEVICE", "plughw:1,0")
AUDIO_OUTPUT_DEVICE = os.environ.get("AUDIO_OUTPUT_DEVICE", "default")
AUDIO_OUTPUT_CARD = int(os.environ.get("AUDIO_OUTPUT_CARD", "0"))  # ALSA card for amixer
AUDIO_SAMPLE_RATE = int(os.environ.get("AUDIO_SAMPLE_RATE", "16000"))

_dry_run_env = os.environ.get("DRY_RUN")
if _dry_run_env is None:
    DRY_RUN = not (TRANSCRIBE_BASE_URL and TRANSCRIBE_API_TOKEN)
else:
    DRY_RUN = _dry_run_env.lower() in ("true", "1", "yes")

LCD_BACKLIGHT = int(os.environ.get("LCD_BACKLIGHT", "70"))
UI_MAX_FPS = int(os.environ.get("UI_MAX_FPS", "4"))

# Speak the assistant response via OpenAI TTS (like whisplay-ai-chatbot)
ENABLE_TTS = os.environ.get("ENABLE_TTS", "true").lower() in ("true", "1", "yes")

# Number of past exchanges (user+assistant pairs) to keep for conversation context
CONVERSATION_HISTORY_LENGTH = int(os.environ.get("CONVERSATION_HISTORY_LENGTH", "5"))

# RMS energy threshold below which audio is considered silence (16-bit range: 0–32768)
SILENCE_RMS_THRESHOLD = float(os.environ.get("SILENCE_RMS_THRESHOLD", "200"))


def print_config():
    """Print non-secret config for debugging."""
    print(f"OPENAI_TRANSCRIBE_MODEL = {OPENAI_TRANSCRIBE_MODEL}")
    print(f"OPENAI_TTS_MODEL        = {OPENAI_TTS_MODEL}")
    print(f"OPENAI_TTS_VOICE        = {OPENAI_TTS_VOICE}")
    print(f"OPENAI_TTS_SPEED        = {OPENAI_TTS_SPEED}")
    print(f"OPENAI_TTS_GAIN_DB      = {OPENAI_TTS_GAIN_DB}")
    print(f"TRANSCRIBE_BASE_URL     = {TRANSCRIBE_BASE_URL}")
    print(f"TRANSCRIBE_HTTP_PATH    = {TRANSCRIBE_HTTP_PATH}")
    print(f"TRANSCRIBE_LANGUAGE     = {TRANSCRIBE_LANGUAGE or '(auto)'}")
    print(f"TRANSCRIBE_API_TOKEN set= {bool(TRANSCRIBE_API_TOKEN)}")
    print(f"STT_MODE                = {STT_MODE}")
    print(f"REALTIME_STT_BASE_URL   = {REALTIME_STT_BASE_URL}")
    print(f"REALTIME_STT_HTTP_PATH  = {REALTIME_STT_HTTP_PATH}")
    print(f"REALTIME_STT_LANGUAGE   = {REALTIME_STT_LANGUAGE or '(auto)'}")
    print(f"REALTIME_STT_CHUNK_MS   = {REALTIME_STT_CHUNK_MS}")
    print(f"REALTIME_STT_CONNECT_S  = {REALTIME_STT_CONNECT_TIMEOUT_SECONDS}")
    print(f"REALTIME_STT_COMMIT_S   = {REALTIME_STT_COMMIT_TIMEOUT_SECONDS}")
    print(f"REALTIME_STT_SHOW_PARTIAL = {REALTIME_STT_SHOW_PARTIAL}")
    print(f"REALTIME_STT_FALLBACK   = {REALTIME_STT_FALLBACK_TO_ONESHOT}")
    print(f"REALTIME_STT_API_TOKEN set= {bool(REALTIME_STT_API_TOKEN)}")
    print(f"TTS_BASE_URL            = {TTS_BASE_URL}")
    print(f"TTS_HTTP_PATH           = {TTS_HTTP_PATH}")
    print(f"TTS_API_TOKEN set       = {bool(TTS_API_TOKEN)}")
    print(f"OPENAI_TTS_INSTRUCTIONS = {OPENAI_TTS_INSTRUCTIONS[:60]}...")
    print(f"OPENCLAW_BASE_URL       = {OPENCLAW_BASE_URL}")
    print(f"AUDIO_DEVICE            = {AUDIO_DEVICE}")
    print(f"AUDIO_OUTPUT_DEVICE     = {AUDIO_OUTPUT_DEVICE}")
    print(f"AUDIO_SAMPLE_RATE       = {AUDIO_SAMPLE_RATE}")
    print(f"DRY_RUN                 = {DRY_RUN}")
    print(f"LCD_BACKLIGHT           = {LCD_BACKLIGHT}")
    print(f"OPENAI_API_KEY set      = {bool(OPENAI_API_KEY)}")
    print(f"OPENCLAW_TOKEN set      = {bool(OPENCLAW_TOKEN)}")
    print(f"ENABLE_TTS              = {ENABLE_TTS}")
    print(f"CONVERSATION_HISTORY    = {CONVERSATION_HISTORY_LENGTH}")
    print(f"SILENCE_RMS_THRESHOLD   = {SILENCE_RMS_THRESHOLD}")
