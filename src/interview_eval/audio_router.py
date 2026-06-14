"""Multi-channel audio capture and per-channel utterance segmentation.

On macOS the interviewer's mic and the candidate's voice (Meet output, tapped
via BlackHole) are combined into a single **Aggregate Device** but on separate
channels. This module reads that device, splits the channels, and segments each
channel into discrete utterances using the same RMS/silence state machine as
``mom_pipeline.live_capture.stream_audio_auto_stop`` — giving speaker separation
("who said what") for free, with no ML diarization.

It also provides a file-backed source (:class:`SimulatedSource`) so the whole
pipeline can be exercised offline against a stereo WAV without a live call.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple

import numpy as np
from scipy.io import wavfile

# Reuse the audio cleanup + WAV encoding already proven in the MoM pipeline.
from mom_pipeline.live_capture import preprocess_audio, array_to_wav
from mom_pipeline.segmenter import UtteranceSegmenter

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_BLOCKSIZE = 4096


# --------------------------------------------------------------------------- #
# Utterance segmentation (pure, hardware-free, fully testable)
# --------------------------------------------------------------------------- #
# UtteranceSegmenter is now defined in src/mom_pipeline/segmenter.py


def utterance_to_wav(audio: np.ndarray, sample_rate: int = DEFAULT_SAMPLE_RATE) -> bytes:
    """Clean (DC-offset/normalize/high-pass) an utterance and encode as WAV bytes."""
    cleaned = preprocess_audio(np.asarray(audio, dtype=np.float32), sample_rate)
    return array_to_wav(cleaned, sample_rate)


# --------------------------------------------------------------------------- #
# Device discovery / diagnostics (lazy sounddevice import = testable module)
# --------------------------------------------------------------------------- #
@dataclass
class DeviceInfo:
    index: int
    name: str
    max_input_channels: int
    default_samplerate: float


def list_input_devices() -> List[DeviceInfo]:
    """Return all input-capable audio devices."""
    import sounddevice as sd  # lazy: avoids hard dependency for pure-logic tests

    devices = sd.query_devices()
    out: List[DeviceInfo] = []
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            out.append(
                DeviceInfo(
                    index=i,
                    name=d["name"],
                    max_input_channels=d["max_input_channels"],
                    default_samplerate=d.get("default_samplerate", DEFAULT_SAMPLE_RATE),
                )
            )
    return out


def list_output_devices() -> List[DeviceInfo]:
    """Return all output-capable audio devices (for routing TTS into Meet's mic)."""
    import sounddevice as sd  # lazy

    devices = sd.query_devices()
    out: List[DeviceInfo] = []
    for i, d in enumerate(devices):
        if d.get("max_output_channels", 0) > 0:
            out.append(
                DeviceInfo(
                    index=i,
                    name=d["name"],
                    max_input_channels=d.get("max_output_channels", 0),
                    default_samplerate=d.get("default_samplerate", DEFAULT_SAMPLE_RATE),
                )
            )
    return out


def _resolve(devices: List[DeviceInfo], name_or_index: str | int, kind: str) -> DeviceInfo:
    if isinstance(name_or_index, int) or str(name_or_index).isdigit():
        idx = int(name_or_index)
        for d in devices:
            if d.index == idx:
                return d
        raise ValueError(f"No {kind} device with index {idx}")
    needle = str(name_or_index).lower()
    matches = [d for d in devices if needle in d.name.lower()]
    if not matches:
        raise ValueError(
            f"No {kind} device matching '{name_or_index}'. "
            f"Available: {', '.join(d.name for d in devices)}"
        )
    return matches[0]


def find_device(name_or_index: str | int) -> DeviceInfo:
    """Resolve an input device by index or case-insensitive name substring."""
    return _resolve(list_input_devices(), name_or_index, "input")


def find_output_device(name_or_index: str | int) -> DeviceInfo:
    """Resolve an output device by index or case-insensitive name substring."""
    return _resolve(list_output_devices(), name_or_index, "output")


def channel_rms(
    device: str | int,
    seconds: float = 4.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> List[float]:
    """Record briefly and return per-channel RMS — the ``check-audio`` diagnostic.

    Used to confirm channel 0 captures the interviewer's mic and the candidate
    channel captures Meet playback, *before* relying on it in a live interview.
    """
    import sounddevice as sd

    dev = find_device(device)
    channels = dev.max_input_channels
    frames = int(seconds * sample_rate)
    recording = sd.rec(
        frames, samplerate=sample_rate, channels=channels, dtype="float32", device=dev.index
    )
    sd.wait()
    return [float(np.sqrt(np.mean(np.square(recording[:, c])))) for c in range(channels)]


def open_input_stream(
    device: str | int | None,
    channels: int,
    callback,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    blocksize: int = DEFAULT_BLOCKSIZE,
):
    """Open (not start) a sounddevice ``InputStream`` for the given device.

    ``device=None`` uses the system default input (used by conduct ``--dry-run``).
    ``callback(indata, frames, time_info, status)`` receives an ``(frames,
    channels)`` float32 array; split channels with ``indata[:, ch]``.
    """
    import sounddevice as sd

    dev_index = find_device(device).index if device is not None else None
    return sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        blocksize=blocksize,
        callback=callback,
        dtype=np.float32,
        device=dev_index,
    )


# --------------------------------------------------------------------------- #
# Offline source for --simulate (no microphone / no live call required)
# --------------------------------------------------------------------------- #
class SimulatedSource:
    """Replay a stereo WAV as per-channel chunks for offline pipeline testing.

    Channel 0 is treated as the interviewer, channel 1 as the candidate
    (matching the live Aggregate Device layout). Yields ``(interviewer_chunk,
    candidate_chunk)`` pairs of length ``blocksize``.
    """

    def __init__(self, wav_path: str, blocksize: int = DEFAULT_BLOCKSIZE):
        rate, data = wavfile.read(wav_path)
        self.sample_rate = int(rate)
        if data.ndim == 1:
            data = np.column_stack([data, np.zeros_like(data)])
        # Normalize integer PCM to float32 [-1, 1].
        if np.issubdtype(data.dtype, np.integer):
            max_int = float(np.iinfo(data.dtype).max)
            data = data.astype(np.float32) / max_int
        else:
            data = data.astype(np.float32)
        self.data = data
        self.blocksize = blocksize

    def chunks(self) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        n = self.data.shape[0]
        for start in range(0, n, self.blocksize):
            block = self.data[start : start + self.blocksize]
            yield block[:, 0].copy(), block[:, 1].copy()


def write_stereo_wav(
    path: str,
    interviewer: np.ndarray,
    candidate: np.ndarray,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> None:
    """Write two mono float32 tracks as a stereo int16 WAV (test-fixture helper)."""
    n = max(interviewer.size, candidate.size)

    def _pad(a: np.ndarray) -> np.ndarray:
        a = np.asarray(a, dtype=np.float32).reshape(-1)
        return np.pad(a, (0, n - a.size)) if a.size < n else a[:n]

    stereo = np.column_stack([_pad(interviewer), _pad(candidate)])
    stereo = np.clip(stereo, -1.0, 1.0)
    wavfile.write(path, sample_rate, np.int16(stereo * 32767))
