import os
from typing import Dict, List, Tuple

from tqdm import tqdm
from openai import OpenAI

from .config import OPENAI_WHISPER_MODEL
from .utils import Retry, ffprobe_duration


def _transcribe_one(client: OpenAI, file_path: str) -> Dict:
    def call():
        with open(file_path, "rb") as f:
            return client.audio.transcriptions.create(
                model=OPENAI_WHISPER_MODEL,
                file=f,
                response_format="verbose_json",
            )

    return Retry(attempts=3, base_delay=1.0, max_delay=8.0).run(call).model_dump()


def transcribe_files(chunk_paths: List[str]) -> Tuple[str, List[Dict]]:
    """Transcribe chunk files with Whisper and merge segments with offsets.
    Returns (raw_text, segments).
    """
    client = OpenAI()
    raw_text_parts = []
    merged_segments = []
    offset = 0.0

    for p in tqdm(chunk_paths, desc="Transcribing"):
        result = _transcribe_one(client, p)
        text = result.get("text", "")
        segments = result.get("segments", [])

        # Adjust segments by offset
        for s in segments:
            s2 = dict(s)
            s2["start"] = (s.get("start") or 0.0) + offset
            s2["end"] = (s.get("end") or 0.0) + offset
            merged_segments.append(s2)

        raw_text_parts.append(text)
        dur = ffprobe_duration(p) or 0.0
        offset += dur

    return ("\n".join(raw_text_parts).strip(), merged_segments)
