import argparse
import os
import sys
import time
import threading
import subprocess
from typing import Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .config import ALLOWED_AUDIO_EXTS, ALLOWED_VIDEO_EXTS


def _ext(path: str) -> str:
    return os.path.splitext(path.lower())[1]


def _is_supported(path: str) -> bool:
    e = _ext(path)
    return e in ALLOWED_AUDIO_EXTS or e in ALLOWED_VIDEO_EXTS


def wait_for_stable(path: str, min_stable_secs: int = 10, timeout_secs: int = 600) -> bool:
    """Wait until a file's size stops changing for min_stable_secs or timeout.
    Returns True if stable, False if timeout.
    """
    start = time.time()
    last_size = -1
    stable_since = None
    while time.time() - start < timeout_secs:
        try:
            size = os.path.getsize(path)
        except FileNotFoundError:
            time.sleep(1)
            continue
        if size == last_size:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= min_stable_secs:
                return True
        else:
            last_size = size
            stable_since = None
        time.sleep(1)
    return False


class Handler(FileSystemEventHandler):
    def __init__(self, output_dir: str, title_prefix: str, participants: str):
        super().__init__()
        self.output_dir = output_dir
        self.title_prefix = title_prefix
        self.participants = participants
        self.processing: Set[str] = set()

    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if not _is_supported(path):
            return
        if path in self.processing:
            return
        self.processing.add(path)
        threading.Thread(target=self._process_file, args=(path,), daemon=True).start()

    def _process_file(self, path: str):
        try:
            if not wait_for_stable(path):
                print(f"Skip unstable or timeout: {path}")
                return
            base = os.path.basename(path)
            title = f"{self.title_prefix}{base}"
            cmd = [
                sys.executable,
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mom_cli.py"),
                "--source",
                path,
                "--title",
                title,
                "--output-dir",
                self.output_dir,
            ]
            if self.participants:
                cmd.extend(["--participants", self.participants])
            print(f"Processing new recording: {path}")
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode != 0:
                print(f"Processing failed for {path}: {proc.stderr}")
            else:
                print(proc.stdout)
        finally:
            self.processing.discard(path)


def main():
    parser = argparse.ArgumentParser(description="Watch a folder and process new Meet recordings")
    parser.add_argument("--watch", required=True, help="Folder to watch (Meet Recordings folder)")
    parser.add_argument("--output-dir", default="outputs", help="Directory for pipeline outputs")
    parser.add_argument("--title-prefix", default="Meet: ", help="Prefix for generated titles")
    parser.add_argument("--participants", default="", help="Comma-separated participants, optional")
    args = parser.parse_args()

    if not os.path.isdir(args.watch):
        raise SystemExit(f"Watch directory not found: {args.watch}")

    observer = Observer()
    handler = Handler(args.output_dir, args.title_prefix, args.participants)
    observer.schedule(handler, args.watch, recursive=False)
    observer.start()
    print(f"Watching for new recordings in: {args.watch}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
