"""Text-to-speech for the AI interviewer.

Synthesizes a question and plays it to a chosen **output device** — which, in a
live interview, is the virtual device Google Meet uses as its microphone, so the
remote candidate hears the AI. Primary engine is OpenAI ``tts-1`` (natural);
``say`` is a free offline fallback. Both decode to a numpy array and play via
sounddevice so they can target a specific device.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from mom_pipeline.llm import get_client

OPENAI_TTS_MODEL = "tts-1"
OPENAI_TTS_RATE = 24000  # tts-1 PCM output is 24 kHz mono s16le
DEFAULT_VOICE = "nova"


def synth_openai(
    text: str, voice: str = DEFAULT_VOICE, api_key: Optional[str] = None, client=None
) -> Tuple[np.ndarray, int]:
    """Synthesize via OpenAI tts-1; return (int16 mono array, sample_rate)."""
    client = client or get_client(api_key)
    resp = client.audio.speech.create(
        model=OPENAI_TTS_MODEL, voice=voice, input=text, response_format="pcm"
    )
    pcm = resp.read()  # raw 24 kHz mono signed 16-bit little-endian
    audio = np.frombuffer(pcm, dtype=np.int16)
    return audio, OPENAI_TTS_RATE


def synth_say(text: str, voice: str = "Samantha") -> Tuple[np.ndarray, int]:
    """Synthesize via macOS ``say`` (offline fallback); return (int16 array, rate)."""
    from scipy.io import wavfile

    if not shutil.which("say"):
        raise RuntimeError("macOS `say` not available")
    with tempfile.TemporaryDirectory() as td:
        aiff = Path(td) / "tts.aiff"
        wav = Path(td) / "tts.wav"
        subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(aiff), "-ar", "24000", "-ac", "1", str(wav)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        rate, data = wavfile.read(wav)
    return data.astype(np.int16), int(rate)


def play_array(audio: np.ndarray, sample_rate: int, device: str | int | None) -> None:
    """Play an audio array to an output device (``None`` = system default), blocking."""
    import sounddevice as sd

    dev_index = None
    if device is not None:
        from .audio_router import find_output_device

        dev_index = find_output_device(device).index
    sd.play(audio, samplerate=sample_rate, device=dev_index)
    sd.wait()


class Speaker:
    """Callable that synthesizes a line and plays it to the Meet-mic device.

    Falls back from OpenAI TTS to ``say`` on error, and finally to printing the
    text (so a session never hard-fails just because audio output is unavailable).
    """

    def __init__(
        self,
        device: str | int | None,
        engine: str = "openai",
        voice: str = DEFAULT_VOICE,
        api_key: Optional[str] = None,
    ) -> None:
        self.device = device
        self.engine = engine
        self.voice = voice
        self.api_key = api_key

    def __call__(self, text: str) -> None:
        if not text or not text.strip():
            return
        try:
            if self.engine == "say":
                audio, rate = synth_say(text)
            else:
                audio, rate = synth_openai(text, voice=self.voice, api_key=self.api_key)
            play_array(audio, rate, self.device)
        except Exception as exc:  # noqa: BLE001 — never let TTS abort the interview
            print(f"[TTS unavailable: {exc}] AI would say: {text}")
