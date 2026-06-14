#!/usr/bin/env python
"""Generate a synthetic two-voice stereo *meeting* WAV for offline MoM testing.

Uses macOS `say` (two voices) + ffmpeg to build a stereo file where channel 0 is
the Host (you) and channel 1 is the Client side — the same layout `meet-mom`
expects from a live Aggregate Device. No microphone or live call needed.

Usage:
    python scripts/make_test_meeting.py [output.wav]
Then:
    meet-mom simulate --wav output.wav --title "Acme Q3 Roadmap Review" \
        --participants "You (Host); Jane Doe (Acme, VP Product)"
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

# (speaker, text) turns of a short client roadmap-review call. "host" = ch0,
# "client" = ch1. Phrased so the MoM has clear decisions/action-items/next-steps.
TURNS = [
    ("host", "Thanks for joining, Jane. Today I want to walk through the Q3 roadmap, "
             "agree on the integration scope, and confirm timelines and budget."),
    ("client", "Sounds good. Our priority is the analytics dashboard and the single "
               "sign-on integration. We need both live before our customer conference in September."),
    ("host", "Understood. We can commit to delivering the analytics dashboard by the "
             "end of August. Single sign-on depends on your security team sharing the SAML metadata."),
    ("client", "I will get our security lead to send the SAML metadata by next Friday. "
               "What about pricing for the additional environments?"),
    ("host", "I will send an updated statement of work with the environment pricing by "
             "Wednesday. Let us also schedule a technical kickoff for early next week."),
    ("client", "Great. Decision-wise we are approving phase one today. The main risk is "
               "the September deadline, so let us keep the kickoff tight. Please send the minutes after this call."),
]

HOST_VOICE = "Alex"
CLIENT_VOICE = "Samantha"
GAP_S = 0.7  # silence between turns


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
    out_path = sys.argv[1] if len(sys.argv) > 1 else "test_meeting.wav"
    gap = np.zeros(int(SAMPLE_RATE * GAP_S), np.float32)

    host_parts: list[np.ndarray] = []
    client_parts: list[np.ndarray] = []

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for speaker, text in TURNS:
            voice = HOST_VOICE if speaker == "host" else CLIENT_VOICE
            audio = _say_to_array(text, voice, tmp)
            span = len(audio) + len(gap)
            if speaker == "host":
                host_parts += [audio, gap]
                client_parts += [np.zeros(span, np.float32)]
            else:
                host_parts += [np.zeros(span, np.float32)]
                client_parts += [audio, gap]

    host = np.concatenate(host_parts)
    client = np.concatenate(client_parts)
    write_stereo_wav(out_path, host, client, sample_rate=SAMPLE_RATE)
    print(f"Wrote {out_path}  ({max(len(host), len(client)) / SAMPLE_RATE:.1f}s, "
          f"{len(TURNS)} turns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
