import os

ALLOWED_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".webm"}
ALLOWED_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
WHISPER_MAX_BYTES = 25 * 1024 * 1024  # conservative default
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_BITRATE = "64k"  # balance quality/size
DEFAULT_CHANNELS = 1
DEFAULT_SEGMENT_SECONDS = 900  # 15 minutes chunks if splitting

OPENAI_WHISPER_MODEL = "whisper-1"
MOM_MODEL = "gpt-4o-mini"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if not OPENAI_API_KEY:
    # We do not raise here; CLI will surface a friendly error.
    pass
