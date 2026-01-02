import os
import shutil
import tempfile
from urllib.parse import urlparse

import requests

from .config import (
    ALLOWED_AUDIO_EXTS,
    ALLOWED_VIDEO_EXTS,
    DEFAULT_BITRATE,
    DEFAULT_CHANNELS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SEGMENT_SECONDS,
    WHISPER_MAX_BYTES,
)
from .utils import ensure_dir, ffmpeg_available, ffprobe_duration, run_cmd


def _ext(path: str) -> str:
    return os.path.splitext(path.lower())[1]


def _is_url(s: str) -> bool:
    try:
        p = urlparse(s)
        return p.scheme in {"http", "https"}
    except Exception:
        return False


def resolve_source(source: str, work_dir: str) -> str:
    """Return a local file path; download if URL.
    Copies local source to work_dir for consistent processing.
    """
    ensure_dir(work_dir)
    if _is_url(source):
        fn = os.path.basename(urlparse(source).path) or "downloaded_input"
        local_path = os.path.join(work_dir, fn)
        with requests.get(source, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        return local_path
    else:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Source not found: {source}")
        target = os.path.join(work_dir, os.path.basename(source))
        shutil.copy2(source, target)
        return target


def validate_and_convert(input_path: str, work_dir: str) -> str:
    """Validate type; if video, convert to MP3 16k mono; if audio, re-encode to target profile.
    Returns path to audio file ready for Whisper.
    """
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg/ffprobe not available. Install via `brew install ffmpeg`.")

    ext = _ext(input_path)
    audio_out = os.path.join(work_dir, "audio_normalized.mp3")

    if ext in ALLOWED_VIDEO_EXTS:
        cmd = (
            f"ffmpeg -y -i \"{input_path}\" -vn -ac {DEFAULT_CHANNELS} "
            f"-ar {DEFAULT_SAMPLE_RATE} -b:a {DEFAULT_BITRATE} \"{audio_out}\""
        )
        proc = run_cmd(cmd)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg video→audio failed: {proc.stderr}")
        return audio_out
    elif ext in ALLOWED_AUDIO_EXTS:
        cmd = (
            f"ffmpeg -y -i \"{input_path}\" -ac {DEFAULT_CHANNELS} "
            f"-ar {DEFAULT_SAMPLE_RATE} -b:a {DEFAULT_BITRATE} \"{audio_out}\""
        )
        proc = run_cmd(cmd)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg audio re-encode failed: {proc.stderr}")
        return audio_out
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def split_if_needed(audio_path: str, work_dir: str) -> list:
    """Split audio into segments if it exceeds Whisper upload limits.
    Returns list of segment file paths (or single-element list).
    """
    size = os.path.getsize(audio_path)
    if size <= WHISPER_MAX_BYTES:
        return [audio_path]

    # Segment into DEFAULT_SEGMENT_SECONDS chunks
    seg_dir = os.path.join(work_dir, "segments")
    ensure_dir(seg_dir)
    segment_template = os.path.join(seg_dir, "part_%03d.mp3")
    cmd = (
        f"ffmpeg -y -i \"{audio_path}\" -f segment -segment_time {DEFAULT_SEGMENT_SECONDS} "
        f"-c copy \"{segment_template}\""
    )
    proc = run_cmd(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg segmenting failed: {proc.stderr}")
    parts = sorted([os.path.join(seg_dir, f) for f in os.listdir(seg_dir) if f.startswith("part_")])

    # As a safeguard, re-encode overly large chunks
    adjusted = []
    for p in parts:
        if os.path.getsize(p) > WHISPER_MAX_BYTES:
            tmp = os.path.join(seg_dir, f"re_{os.path.basename(p)}")
            cmd2 = (
                f"ffmpeg -y -i \"{p}\" -ac {DEFAULT_CHANNELS} -ar {DEFAULT_SAMPLE_RATE} -b:a {DEFAULT_BITRATE} \"{tmp}\""
            )
            proc2 = run_cmd(cmd2)
            if proc2.returncode != 0:
                raise RuntimeError(f"ffmpeg re-encode segment failed: {proc2.stderr}")
            adjusted.append(tmp)
        else:
            adjusted.append(p)
    return adjusted
