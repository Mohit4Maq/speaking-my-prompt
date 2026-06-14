"""Meeting session: transcribe both channels into a speaker-labeled transcript.

:class:`MeetingSession` is the pure, dependency-injected core (no audio, no
threads) so it is fully unit-testable. It accepts Host/Client utterances, keeps
an ordered timestamped transcript, and at the end generates the MoM.

Two drivers feed it utterances (both reuse ``interview_eval``'s proven audio
engine — see Decision A in docs/MEETING_MOM_PLAN.md):

* :func:`run_simulated` — replays a stereo WAV synchronously (offline E2E).
* :func:`run_live` — opens the Aggregate Device, segments both channels on a
  background thread, renders an optional live transcript panel on the main thread.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from mom_pipeline.live_transcribe import transcribe_audio

from interview_eval.audio_router import (
    DEFAULT_BLOCKSIZE,
    DEFAULT_SAMPLE_RATE,
    SimulatedSource,
    UtteranceSegmenter,
    open_input_stream,
    utterance_to_wav,
)

from .meeting import Meeting
from .mom import DEFAULT_MOM_MODEL, generate_mom

EventHandler = Callable[[Dict[str, Any]], None]

HOST = "Host"
CLIENT = "Client"


def _fmt_ts(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class MeetingSession:
    """Stateful core: accepts host/client utterances, builds a transcript, makes a MoM."""

    def __init__(
        self,
        meeting: Meeting,
        language: str = "en",
        model: str = DEFAULT_MOM_MODEL,
        api_key: Optional[str] = None,
        transcribe_fn: Optional[Callable[[bytes], str]] = None,
        mom_fn: Optional[Callable[[str, Meeting], Dict[str, Any]]] = None,
        on_event: Optional[EventHandler] = None,
    ) -> None:
        self.meeting = meeting
        self.language = language
        self.model = model
        self._api_key = api_key
        self.transcribe_fn = transcribe_fn or self._default_transcribe
        self.mom_fn = mom_fn or self._default_mom
        self.on_event = on_event or (lambda ev: None)

        # Ordered transcript of (elapsed_seconds, speaker, text).
        self.transcript: List[Tuple[float, str, str]] = []
        self._start = time.monotonic()
        self._elapsed_override: Optional[float] = None  # set by simulated driver
        self._lock = threading.Lock()

    # -- default dependencies ------------------------------------------------ #
    def _default_transcribe(self, wav_bytes: bytes) -> str:
        text, _ = transcribe_audio(wav_bytes, language=self.language)
        return text

    def _default_mom(self, transcript_text: str, meeting: Meeting) -> Dict[str, Any]:
        return generate_mom(transcript_text, meeting, model=self.model)

    # -- utterance handlers -------------------------------------------------- #
    def on_host_utterance(self, wav_bytes: bytes) -> None:
        self._add(HOST, wav_bytes)

    def on_client_utterance(self, wav_bytes: bytes) -> None:
        self._add(CLIENT, wav_bytes)

    def _add(self, speaker: str, wav_bytes: bytes) -> None:
        text = self.transcribe_fn(wav_bytes).strip()
        if not text:
            return
        ts = self._elapsed()
        with self._lock:
            self.transcript.append((ts, speaker, text))
        self.on_event({"type": "utterance", "ts": ts, "speaker": speaker, "text": text})

    def _elapsed(self) -> float:
        if self._elapsed_override is not None:
            return self._elapsed_override
        return time.monotonic() - self._start

    # -- transcript views ---------------------------------------------------- #
    def transcript_text(self) -> str:
        """Speaker-labeled, timestamped lines: ``[HH:MM:SS] Host: …``."""
        with self._lock:
            rows = list(self.transcript)
        return "\n".join(f"[{_fmt_ts(ts)}] {spk}: {txt}" for ts, spk, txt in rows)

    def finalize(self) -> Dict[str, Any]:
        """Generate and return the MoM dict from the accumulated transcript."""
        text = self.transcript_text()
        self.on_event({"type": "generating", "chars": len(text)})
        return self.mom_fn(text, self.meeting)


# --------------------------------------------------------------------------- #
# Driver: offline replay of a stereo WAV (ch0 host, ch1 client)
# --------------------------------------------------------------------------- #
def run_simulated(
    session: MeetingSession, wav_path: str, blocksize: int = DEFAULT_BLOCKSIZE
) -> Dict[str, Any]:
    """Feed a stereo WAV through the pipeline synchronously; return the MoM dict."""
    src = SimulatedSource(wav_path, blocksize=blocksize)
    seg_h = UtteranceSegmenter(sample_rate=src.sample_rate)
    seg_c = UtteranceSegmenter(sample_rate=src.sample_rate)

    elapsed = 0.0
    chunk_dt = blocksize / src.sample_rate
    for host_chunk, client_chunk in src.chunks():
        session._elapsed_override = elapsed  # deterministic timestamps from playback
        utt_h = seg_h.feed(host_chunk)
        if utt_h is not None:
            session.on_host_utterance(utterance_to_wav(utt_h, src.sample_rate))
        utt_c = seg_c.feed(client_chunk)
        if utt_c is not None:
            session.on_client_utterance(utterance_to_wav(utt_c, src.sample_rate))
        elapsed += chunk_dt

    for seg, handler in ((seg_h, session.on_host_utterance), (seg_c, session.on_client_utterance)):
        tail = seg.flush()
        if tail is not None:
            handler(utterance_to_wav(tail, src.sample_rate))

    session._elapsed_override = None
    return session.finalize()


# --------------------------------------------------------------------------- #
# Driver: live capture from the Aggregate Device
# --------------------------------------------------------------------------- #
def run_live(
    session: MeetingSession,
    device: str | int,
    host_channel: int = 0,
    client_channel: int = 1,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    blocksize: int = DEFAULT_BLOCKSIZE,
    render_fn: Optional[Callable[[MeetingSession], Any]] = None,
) -> Dict[str, Any]:
    """Run a live meeting capture until Ctrl+C, then generate and return the MoM.

    A background thread segments both channels and drives transcription; the main
    thread renders the live transcript panel (if ``render_fn`` given) so it stays
    responsive regardless of API latency. Structure mirrors
    ``interview_eval.session.run_live``.
    """
    channels_needed = max(host_channel, client_channel) + 1
    audio_q: "queue.Queue[Optional[Tuple[Any, Any]]]" = queue.Queue()

    def audio_callback(indata, frames, time_info, status):  # noqa: ANN001
        if status:
            print(f"Audio status: {status}")
        audio_q.put((indata[:, host_channel].copy(), indata[:, client_channel].copy()))

    seg_h = UtteranceSegmenter(sample_rate=sample_rate)
    seg_c = UtteranceSegmenter(sample_rate=sample_rate)
    stop_event = threading.Event()

    def consumer() -> None:
        while not stop_event.is_set():
            try:
                item = audio_q.get(timeout=0.25)
            except queue.Empty:
                continue
            if item is None:
                break
            host_chunk, client_chunk = item
            utt_h = seg_h.feed(host_chunk)
            if utt_h is not None:
                session.on_host_utterance(utterance_to_wav(utt_h, sample_rate))
            utt_c = seg_c.feed(client_chunk)
            if utt_c is not None:
                session.on_client_utterance(utterance_to_wav(utt_c, sample_rate))

    stream = open_input_stream(
        device, channels_needed, audio_callback, sample_rate=sample_rate, blocksize=blocksize
    )
    worker = threading.Thread(target=consumer, daemon=True)
    stream.start()
    worker.start()

    try:
        if render_fn is not None:
            from rich.live import Live

            with Live(render_fn(session), refresh_per_second=4, screen=False) as live:
                while not stop_event.is_set():
                    live.update(render_fn(session))
                    time.sleep(0.25)
        else:
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nEnding capture… generating minutes.")
    finally:
        stop_event.set()
        audio_q.put(None)
        stream.stop()
        stream.close()
        worker.join(timeout=2.0)

    return session.finalize()
