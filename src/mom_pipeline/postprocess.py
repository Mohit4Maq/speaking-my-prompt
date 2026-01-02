from typing import Dict, List, Tuple

from .utils import format_seconds


FILLERS = {
    "um",
    "uh",
    "like",
    "you know",
    "i mean",
    "sort of",
    "kind of",
    "right",
    "okay",
}


def _clean_segment_text(text: str) -> str:
    t = text.strip()
    # simple filler removal
    for f in FILLERS:
        t = t.replace(f, "")
        t = t.replace(f.capitalize(), "")
    # collapse double spaces
    while "  " in t:
        t = t.replace("  ", " ")
    return t.strip()


def normalize_segments(segments: List[Dict]) -> List[Dict]:
    out = []
    for s in segments:
        text = _clean_segment_text(s.get("text", ""))
        if not text:
            continue
        start = float(s.get("start") or 0.0)
        end = float(s.get("end") or 0.0)
        out.append(
            {
                "start": start,
                "end": end,
                "start_ts": format_seconds(start),
                "end_ts": format_seconds(end),
                "text": text,
                "speaker": None,  # do not hallucinate
            }
        )
    return out


def segments_to_text(segments: List[Dict]) -> str:
    parts = []
    for s in segments:
        parts.append(s["text"])
    return "\n".join(parts).strip()


def chunk_text(text: str, max_chars: int = 8000) -> List[str]:
    # Safe chunking for long transcripts; split on paragraph boundaries
    if len(text) <= max_chars:
        return [text]
    chunks = []
    buf = []
    size = 0
    for line in text.splitlines():
        if size + len(line) + 1 > max_chars:
            chunks.append("\n".join(buf))
            buf = []
            size = 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks
