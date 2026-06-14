"""Interview session orchestration: transcribe → match → buffer → score.

:class:`InterviewSession` holds the dependency-injected core logic (no audio,
no threads) so it is fully unit-testable. Two drivers feed it utterances:

* :func:`run_simulated` — replays a stereo WAV synchronously (offline E2E).
* :func:`run_live` — opens the macOS Aggregate Device, segments both channels
  on a background thread, and renders the live TUI on the main thread.

Answer buffering: consecutive candidate utterances accumulate into a single
answer for the active question. The answer is scored when the interviewer asks
the next (matched) question, or when the session ends.
"""
from __future__ import annotations

import queue
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from mom_pipeline.live_transcribe import transcribe_audio

from .audio_router import (
    DEFAULT_BLOCKSIZE,
    DEFAULT_SAMPLE_RATE,
    SimulatedSource,
    UtteranceSegmenter,
    open_input_stream,
    utterance_to_wav,
)
from .question_bank import Question, QuestionBank
from .report import aggregate, build_report
from .scorer import score_answer

EventHandler = Callable[[Dict[str, Any]], None]

# Multi-word interviewer backchannels that should NOT start a new question in
# freeform mode (single-word ones are caught by the length gate).
_BACKCHANNELS = {
    "okay got it", "that makes sense", "okay that makes sense", "okay makes sense",
    "yeah makes sense", "okay thank you", "okay thanks a lot", "got it thanks",
    "okay go on", "please go on", "go right ahead", "okay go ahead",
}


class InterviewSession:
    """Stateful core: accepts interviewer/candidate utterances, produces a report."""

    def __init__(
        self,
        bank: Optional[QuestionBank],
        competencies: List[Dict[str, Any]],
        role_title: str = "",
        candidate_name: str = "",
        api_key: Optional[str] = None,
        language: str = "en",
        freeform: bool = False,
        min_question_words: int = 4,
        transcribe_fn: Optional[Callable[[bytes], str]] = None,
        score_fn: Optional[Callable[[str, str, List[Dict[str, Any]]], Dict[str, Any]]] = None,
        on_event: Optional[EventHandler] = None,
    ) -> None:
        self.bank = bank
        self.freeform = freeform
        self.min_question_words = min_question_words
        self._freeform_qn = 0
        self.competencies = competencies
        self.role_title = role_title
        self.candidate_name = candidate_name
        self.language = language
        self._api_key = api_key
        self.transcribe_fn = transcribe_fn or self._default_transcribe
        self.score_fn = score_fn or self._default_score
        self.on_event = on_event or (lambda ev: None)

        self.active_question: Optional[Question] = None
        self.active_competencies: List[Dict[str, Any]] = []
        self._answer_parts: List[str] = []
        self._active_followups: List[str] = []
        self.answers: List[Dict[str, Any]] = []
        self.transcript: List[Tuple[str, str]] = []
        self._lock = threading.Lock()

    # -- default dependencies ------------------------------------------------ #
    def _default_transcribe(self, wav_bytes: bytes) -> str:
        text, _ = transcribe_audio(wav_bytes, language=self.language)
        return text

    def _default_score(
        self, question: str, answer: str, comps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        # In freeform the question isn't mapped to competencies, so let the
        # scorer judge only the ones the answer actually addresses.
        return score_answer(
            question, answer, comps, self.role_title,
            only_relevant=self.freeform, api_key=self._api_key,
        )

    # -- competency selection ------------------------------------------------ #
    def _competencies_for(self, question: Optional[Question]) -> List[Dict[str, Any]]:
        if question is None or not question.competencies:
            return self.competencies  # unmapped → judge against the full rubric
        ids = set(question.competencies)
        subset = [c for c in self.competencies if c["id"] in ids]
        return subset or self.competencies

    # -- utterance handlers -------------------------------------------------- #
    def on_interviewer_utterance(self, wav_bytes: bytes) -> None:
        text = self.transcribe_fn(wav_bytes).strip()
        if not text:
            return
        with self._lock:
            self.transcript.append(("interviewer", text))
        self.on_event({"type": "interviewer", "text": text})

        if self.freeform:
            # No bank: your transcribed question is the anchor. A substantial
            # interviewer turn starts a new question; short backchannels don't.
            if self._is_new_question(text):
                self._finalize_current_answer()
                self._freeform_qn += 1
                question = Question(id=f"q{self._freeform_qn}", question=text, competencies=[])
                with self._lock:
                    self.active_question = question
                    self.active_competencies = self._competencies_for(question)
                self.on_event({"type": "question", "question": question, "similarity": 1.0})
            return

        question, similarity = self.bank.match(text)
        if question is not None:
            self._finalize_current_answer()  # score the previous question's answer
            with self._lock:
                self.active_question = question
                self.active_competencies = self._competencies_for(question)
            self.on_event(
                {"type": "question", "question": question, "similarity": similarity}
            )

    def _is_new_question(self, text: str) -> bool:
        """Heuristic gate: is this interviewer turn a new question vs a backchannel?"""
        words = re.findall(r"[a-z0-9']+", text.lower())
        if len(words) < self.min_question_words:
            return False
        return " ".join(words) not in _BACKCHANNELS

    def on_candidate_utterance(self, wav_bytes: bytes) -> None:
        text = self.transcribe_fn(wav_bytes).strip()
        if not text:
            return
        with self._lock:
            self.transcript.append(("candidate", text))
            self._answer_parts.append(text)
        self.on_event({"type": "candidate", "text": text})

    def _finalize_current_answer(self) -> None:
        with self._lock:
            if self.active_question is None or not self._answer_parts:
                self._answer_parts = []
                self._active_followups = []
                return
            question = self.active_question
            comps = self.active_competencies
            answer_text = " ".join(self._answer_parts)
            followups = list(self._active_followups)
            self._answer_parts = []
            self._active_followups = []

        result = self.score_fn(question.question, answer_text, comps)
        entry = {
            "question_id": question.id,
            "question": question.question,
            "answer": answer_text,
            "followups": followups,
            **result,
        }
        with self._lock:
            self.answers.append(entry)
        self.on_event({"type": "score", "entry": entry})

    # -- AI-interviewer (conduct) controls ----------------------------------- #
    def advance_to(self, question: Question) -> None:
        """Score the previous answer and make ``question`` the active question.

        Used when the AI (not the candidate's interviewer) asks the next
        question, so the active question is known exactly — no speech matching.
        """
        self._finalize_current_answer()
        with self._lock:
            self.active_question = question
            self.active_competencies = self._competencies_for(question)
        self.on_event({"type": "question", "question": question, "similarity": 1.0})

    def add_followup(self, text: str) -> None:
        """Record an AI follow-up asked within the current question (for the report)."""
        with self._lock:
            self._active_followups.append(text)
        self.transcript.append(("interviewer", f"(follow-up) {text}"))
        self.on_event({"type": "followup", "text": text})

    def current_answer_text(self) -> str:
        with self._lock:
            return " ".join(self._answer_parts)

    # -- live snapshot for the TUI ------------------------------------------- #
    def snapshot_scores(self) -> Dict[str, Any]:
        with self._lock:
            answers = list(self.answers)
        return aggregate(self.competencies, answers)

    def finalize(self) -> Dict[str, Any]:
        """Score the last buffered answer and return the full report object."""
        self._finalize_current_answer()
        with self._lock:
            answers = list(self.answers)
        return build_report(self.role_title, self.competencies, answers, self.candidate_name)


# --------------------------------------------------------------------------- #
# Driver: offline replay of a stereo WAV (ch0 interviewer, ch1 candidate)
# --------------------------------------------------------------------------- #
def run_simulated(session: InterviewSession, wav_path: str, blocksize: int = DEFAULT_BLOCKSIZE) -> Dict[str, Any]:
    """Feed a stereo WAV through the full pipeline synchronously; return the report."""
    src = SimulatedSource(wav_path, blocksize=blocksize)
    seg_i = UtteranceSegmenter(sample_rate=src.sample_rate)
    seg_c = UtteranceSegmenter(sample_rate=src.sample_rate)

    for interviewer_chunk, candidate_chunk in src.chunks():
        utt_i = seg_i.feed(interviewer_chunk)
        if utt_i is not None:
            session.on_interviewer_utterance(utterance_to_wav(utt_i, src.sample_rate))
        utt_c = seg_c.feed(candidate_chunk)
        if utt_c is not None:
            session.on_candidate_utterance(utterance_to_wav(utt_c, src.sample_rate))

    for seg, handler in ((seg_i, session.on_interviewer_utterance), (seg_c, session.on_candidate_utterance)):
        tail = seg.flush()
        if tail is not None:
            handler(utterance_to_wav(tail, src.sample_rate))

    return session.finalize()


# --------------------------------------------------------------------------- #
# Driver: live capture from the Aggregate Device
# --------------------------------------------------------------------------- #
def run_live(
    session: InterviewSession,
    device: str | int,
    interviewer_channel: int = 0,
    candidate_channel: int = 1,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    blocksize: int = DEFAULT_BLOCKSIZE,
    render_fn: Optional[Callable[[InterviewSession], Any]] = None,
) -> Dict[str, Any]:
    """Run a live interview until Ctrl+C, then return the report.

    A background thread segments both channels and drives transcription/scoring;
    the main thread renders the TUI (if ``render_fn`` given) so it stays
    responsive regardless of API latency.
    """
    channels_needed = max(interviewer_channel, candidate_channel) + 1
    audio_q: "queue.Queue[Optional[Tuple[Any, Any]]]" = queue.Queue()

    def audio_callback(indata, frames, time_info, status):  # noqa: ANN001
        if status:
            print(f"Audio status: {status}")
        audio_q.put(
            (indata[:, interviewer_channel].copy(), indata[:, candidate_channel].copy())
        )

    seg_i = UtteranceSegmenter(sample_rate=sample_rate)
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
            interviewer_chunk, candidate_chunk = item
            utt_i = seg_i.feed(interviewer_chunk)
            if utt_i is not None:
                session.on_interviewer_utterance(utterance_to_wav(utt_i, sample_rate))
            utt_c = seg_c.feed(candidate_chunk)
            if utt_c is not None:
                session.on_candidate_utterance(utterance_to_wav(utt_c, sample_rate))

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
        print("\nEnding interview… generating report.")
    finally:
        stop_event.set()
        audio_q.put(None)
        stream.stop()
        stream.close()
        worker.join(timeout=2.0)

    return session.finalize()


# --------------------------------------------------------------------------- #
# Driver: AI interviewer (conduct) — AI voices questions, human paces it
# --------------------------------------------------------------------------- #
# Minimum RMS for a captured answer to be treated as speech (else: no answer,
# avoids Whisper hallucinating text from silence).
_ANSWER_RMS_FLOOR = 0.005


def run_conduct(
    session: InterviewSession,
    questions: List[Question],
    speak: Callable[[str], None],
    input_device: str | int | None,
    candidate_channel: int = 0,
    followup_fn: Optional[Callable[[str, str], str]] = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    blocksize: int = DEFAULT_BLOCKSIZE,
    prompt_fn: Callable[[str], str] = input,
) -> Dict[str, Any]:
    """Run a human-paced, AI-voiced interview; return the report.

    Capture is **push-to-advance and echo-safe**, which fixes two conduct-mode
    hazards:

    * **Echo** — the mic is muted (``capturing`` cleared) whenever the AI is
      speaking, so the spoken question is never captured as the candidate's
      answer (critical in ``--dry-run`` where speakers feed the mic).
    * **Off-by-one** — the answer is the single audio span captured between "AI
      finished asking" and your Enter press, transcribed synchronously *before*
      advancing. No VAD race against the keystroke.

    Controls: Enter/n = next · f = AI follow-up · r = repeat · q = finish.
    """
    capturing = threading.Event()
    lock = threading.Lock()
    collected: List[np.ndarray] = []

    def audio_callback(indata, frames, time_info, status):  # noqa: ANN001
        if status:
            print(f"Audio status: {status}")
        if capturing.is_set():
            with lock:
                collected.append(indata[:, candidate_channel].copy())

    def _clear() -> None:
        with lock:
            collected.clear()

    def begin_listen() -> None:
        _clear()
        capturing.set()

    def speak_safely(text: str) -> None:
        """Speak with the mic muted so the AI voice can't pollute the answer."""
        was = capturing.is_set()
        capturing.clear()
        speak(text)
        _clear()  # drop any straggler chunks captured during the toggle race
        if was:
            capturing.set()

    def end_and_capture() -> None:
        """Stop listening and fold the captured span into the current answer."""
        capturing.clear()
        with lock:
            data = list(collected)
            collected.clear()
        if not data:
            return
        audio = np.concatenate(data)
        if float(np.sqrt(np.mean(np.square(audio)))) < _ANSWER_RMS_FLOOR:
            return  # effectively silence → treat as no answer
        print("   📝 transcribing answer…")
        session.on_candidate_utterance(utterance_to_wav(audio, sample_rate))

    stream = open_input_stream(
        input_device, candidate_channel + 1, audio_callback,
        sample_rate=sample_rate, blocksize=blocksize,
    )
    stream.start()

    controls = "[Enter]=next  f=follow-up  r=repeat  q=finish > "
    try:
        prompt_fn("Press Enter to begin the interview… ")
        for question in questions:
            session.advance_to(question)
            print(f"\n🔊 AI asks: {question.question}")
            speak_safely(question.question)
            begin_listen()  # capture the candidate's answer from here until Enter
            advance = False
            while not advance:
                cmd = prompt_fn(controls).strip().lower()
                if cmd in ("", "n"):
                    end_and_capture()
                    advance = True
                elif cmd == "r":
                    speak_safely(question.question)  # keeps the capture window open
                elif cmd == "f":
                    end_and_capture()  # bank what's been said so the follow-up has context
                    fu = (followup_fn or (lambda q, a: ""))(
                        question.question, session.current_answer_text()
                    )
                    if fu:
                        session.add_followup(fu)
                        print(f"🔊 AI follow-up: {fu}")
                        speak_safely(fu)
                    begin_listen()  # capture the answer to the follow-up too
                elif cmd == "q":
                    end_and_capture()
                    raise _StopConduct
        print("\nReached end of question bank.")
    except (_StopConduct, KeyboardInterrupt):
        print("\nFinishing interview… generating report.")
    finally:
        capturing.clear()
        stream.stop()
        stream.close()

    return session.finalize()


class _StopConduct(Exception):
    """Internal signal to end the conduct loop on the 'q' command."""
