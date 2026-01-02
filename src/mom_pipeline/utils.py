import json
import os
import shlex
import subprocess
import time
from datetime import datetime
from typing import Optional


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def run_cmd(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def ffmpeg_available() -> bool:
    return run_cmd("ffmpeg -version").returncode == 0 and run_cmd("ffprobe -version").returncode == 0


def format_seconds(seconds: float) -> str:
    # Format as HH:MM:SS.mmm
    millis = int((seconds - int(seconds)) * 1000)
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}.{millis:03d}"


def size_to_str(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} TB"


def ffprobe_duration(file_path: str) -> Optional[float]:
    cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 \"{file_path}\""
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except Exception:
        return None


def safe_json_dump(data, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def now_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


class Retry:
    def __init__(self, attempts=3, base_delay=1.0, max_delay=8.0):
        self.attempts = attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    def backoff(self, i):
        return min(self.base_delay * (2 ** i), self.max_delay)

    def run(self, fn):
        last_exc = None
        for i in range(self.attempts):
            try:
                return fn()
            except Exception as e:
                last_exc = e
                delay = self.backoff(i)
                time.sleep(delay)
        if last_exc:
            raise last_exc
