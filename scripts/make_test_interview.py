#!/usr/bin/env python
"""Generate a synthetic two-voice stereo interview WAV for offline testing.

Uses macOS `say` (two voices) + ffmpeg to build a stereo file where channel 0 is
the interviewer and channel 1 is the candidate — the same layout `hire-eval`
expects from a live Aggregate Device. No microphone or live call needed.

Usage:
    python scripts/make_test_interview.py [output.wav]
Then:
    hire-eval simulate --jd examples/jd.txt --questions examples/questions.yaml \
        --wav output.wav --candidate "Test Candidate"
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from interview_eval.audio_router import write_stereo_wav  # noqa: E402

SAMPLE_RATE = 16000

# (interviewer question, candidate answer). Questions are phrased to match the
# examples/questions.yaml bank so the embedding matcher pairs them correctly.
TURNS = [
    (
        "Tell me about the difference between REST and GraphQL, and when you would choose each one.",
        "REST is stateless and uses HTTP methods on resources, but it can over fetch data. "
        "GraphQL lets the client request exactly the fields it needs in one query, which avoids "
        "over fetching, though it adds caching complexity. I would pick REST for simple public "
        "APIs and GraphQL for rich client apps with varied data needs.",
    ),
    (
        "Walk me through how you debugged a hard production issue under pressure.",
        "We had a sudden spike in payment failures. I started from the error metrics, formed a "
        "hypothesis that a downstream timeout was the cause, checked the traces, and found a "
        "database connection pool exhaustion. I added back pressure and increased the pool, then "
        "wrote a regression test and a runbook so it would not happen again.",
    ),
]

INTERVIEWER_VOICE = "Alex"
CANDIDATE_VOICE = "Samantha"
GAP_S = 0.8  # silence between turns


def _say_to_array(text: str, voice: str, tmp: Path) -> np.ndarray:
    aiff = tmp / "speech.aiff"
    wav = tmp / "speech.wav"
    subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(aiff), "-ar", str(SAMPLE_RATE), "-ac", "1", str(wav)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _, data = wavfile.read(wav)
    return data.astype(np.float32) / 32767.0


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "test_interview.wav"
    gap = np.zeros(int(SAMPLE_RATE * GAP_S), np.float32)

    interviewer_parts: list[np.ndarray] = []
    candidate_parts: list[np.ndarray] = []

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for question, answer in TURNS:
            q = _say_to_array(question, INTERVIEWER_VOICE, tmp)
            a = _say_to_array(answer, CANDIDATE_VOICE, tmp)
            # Interviewer speaks the question; candidate is silent for that span.
            interviewer_parts += [q, gap, np.zeros(len(a) + len(gap), np.float32)]
            # Candidate is silent during the question, then answers.
            candidate_parts += [np.zeros(len(q) + len(gap), np.float32), a, gap]

    interviewer = np.concatenate(interviewer_parts)
    candidate = np.concatenate(candidate_parts)
    write_stereo_wav(out_path, interviewer, candidate, sample_rate=SAMPLE_RATE)
    print(f"Wrote {out_path}  ({max(len(interviewer), len(candidate)) / SAMPLE_RATE:.1f}s, "
          f"{len(TURNS)} Q&A turns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
