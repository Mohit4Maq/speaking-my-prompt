"""Utterance segmentation for voice capture.

Stateful segmenter: feed audio chunks, get back complete utterances.
Prevents premature cuts and enforces duration bounds.
"""
from __future__ import annotations

from typing import List, Optional
import numpy as np

DEFAULT_SAMPLE_RATE = 16000

class UtteranceSegmenter:
    """Stateful segmenter: feed audio chunks, get back complete utterances.

    A continuous adaptation of the auto-stop logic. Call :meth:`feed` with successive mono chunks
    from one channel; it returns a concatenated utterance (float32 array) once
    speech is followed by ``silence_duration`` seconds of silence, otherwise
    ``None``. Durations are tracked from sample counts (not wall-clock), so the
    same code drives both live capture and offline file replay deterministically.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        silence_threshold: float = 0.010,
        silence_duration: float = 1.2,
        min_utterance: float = 0.4,
        max_utterance: float = 60.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.min_utterance = min_utterance
        self.max_utterance = max_utterance
        self._reset()

    def _reset(self) -> None:
        self._buffer: List[np.ndarray] = []
        self._speech_started = False
        self._silence_run = 0.0  # trailing silence in seconds
        self._captured = 0.0  # speech captured since onset, in seconds
        self._preroll: Optional[np.ndarray] = None

    def feed(self, chunk: np.ndarray) -> Optional[np.ndarray]:
        """Feed one mono chunk; return a finished utterance array or ``None``."""
        chunk = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if chunk.size == 0:
            return None
        dur = chunk.size / self.sample_rate
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        voiced = rms > self.silence_threshold

        if not self._speech_started:
            if voiced:
                self._speech_started = True
                if self._preroll is not None:
                    self._buffer.append(self._preroll)  # keep speech onset
                self._buffer.append(chunk)
                self._captured = dur
                self._silence_run = 0.0
            else:
                self._preroll = chunk  # remember last silent block as pre-roll
            return None

        self._buffer.append(chunk)
        self._captured += dur
        if voiced:
            self._silence_run = 0.0
        else:
            self._silence_run += dur

        if self._captured >= self.max_utterance:
            return self._emit()
        if self._silence_run >= self.silence_duration and self._captured >= self.min_utterance:
            return self._emit()
        return None

    def flush(self) -> Optional[np.ndarray]:
        """Emit any buffered speech (e.g. at end of stream); else ``None``."""
        if self._speech_started and self._captured >= self.min_utterance:
            return self._emit()
        self._reset()
        return None

    def _emit(self) -> np.ndarray:
        audio = np.concatenate(self._buffer) if self._buffer else np.zeros(0, np.float32)
        self._reset()
        return audio
