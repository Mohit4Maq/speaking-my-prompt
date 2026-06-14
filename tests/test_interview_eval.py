"""Unit tests for the interview_eval package (no audio hardware, no real API)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from interview_eval.audio_router import UtteranceSegmenter, write_stereo_wav
from interview_eval.jd_parser import normalize_weights
from interview_eval.report import aggregate, hire_band, render_markdown
from interview_eval.scorer import score_answer, _clamp_score
from interview_eval.question_bank import (
    Question,
    QuestionBank,
    align_question_competencies,
)
from interview_eval.session import InterviewSession, run_conduct, run_simulated


# --------------------------------------------------------------------------- #
# UtteranceSegmenter (pure math, fully testable)
# --------------------------------------------------------------------------- #
def _chunk(amplitude: float, sample_rate: int, dur: float = 0.1) -> np.ndarray:
    n = int(sample_rate * dur)
    if amplitude == 0:
        return np.zeros(n, dtype=np.float32)
    return (np.ones(n, dtype=np.float32) * amplitude)


def test_segmenter_emits_after_trailing_silence():
    sr = 16000
    seg = UtteranceSegmenter(
        sample_rate=sr, silence_threshold=0.01, silence_duration=0.3, min_utterance=0.2
    )
    out = None
    # 2 silent, 5 voiced, then silence until it emits.
    for _ in range(2):
        assert seg.feed(_chunk(0.0, sr)) is None
    for _ in range(5):
        assert seg.feed(_chunk(0.5, sr)) is None
    # Trailing silence accumulates; emits once >= silence_duration (0.3s = 3 chunks).
    results = [seg.feed(_chunk(0.0, sr)) for _ in range(4)]
    out = next((r for r in results if r is not None), None)
    assert out is not None
    # Should contain roughly the 5 voiced chunks (+ ~1 preroll/trailing).
    assert out.size >= int(sr * 0.5)


def test_segmenter_ignores_pure_silence():
    sr = 16000
    seg = UtteranceSegmenter(sample_rate=sr, silence_threshold=0.01)
    for _ in range(20):
        assert seg.feed(_chunk(0.0, sr)) is None
    assert seg.flush() is None


def test_segmenter_flush_returns_pending_speech():
    sr = 16000
    seg = UtteranceSegmenter(sample_rate=sr, silence_threshold=0.01, min_utterance=0.2)
    for _ in range(5):
        seg.feed(_chunk(0.5, sr))
    tail = seg.flush()
    assert tail is not None and tail.size > 0


# --------------------------------------------------------------------------- #
# jd_parser weight normalization
# --------------------------------------------------------------------------- #
def test_normalize_weights_sums_to_one():
    comps = [{"weight": 3}, {"weight": 1}, {"weight": 1}]
    normalize_weights(comps)
    assert abs(sum(c["weight"] for c in comps) - 1.0) < 1e-9
    assert abs(comps[0]["weight"] - 0.6) < 1e-9


def test_normalize_weights_all_zero_splits_evenly():
    comps = [{"weight": 0}, {"weight": 0}]
    normalize_weights(comps)
    assert all(abs(c["weight"] - 0.5) < 1e-9 for c in comps)


# --------------------------------------------------------------------------- #
# report aggregation + hire bands
# --------------------------------------------------------------------------- #
def test_aggregate_weighted_overall():
    competencies = [
        {"id": "python", "name": "Python", "weight": 0.5},
        {"id": "design", "name": "Design", "weight": 0.5},
    ]
    answers = [
        {"per_competency": {"python": 8, "design": 6}},
        {"per_competency": {"python": 8}},
    ]
    summary = aggregate(competencies, answers)
    # python avg = 8, design avg = 6 -> weighted 0.5*8 + 0.5*6 = 7.0
    assert summary["overall"] == 7.0
    assert summary["per_competency"]["python"]["n"] == 2
    assert summary["band"] == "Lean hire"


def test_hire_bands():
    assert hire_band(8.5) == "Strong hire"
    assert hire_band(7.0) == "Lean hire"
    assert hire_band(5.5) == "Borderline"
    assert hire_band(3.0) == "No hire"
    assert hire_band(None) == "Insufficient data"


def test_render_markdown_smoke():
    report = {
        "role_title": "Backend Engineer",
        "candidate": "Jane",
        "generated_at": "2026-06-10T00:00:00+00:00",
        "overall": 7.0,
        "band": "Lean hire",
        "competencies": {"python": {"name": "Python", "weight": 0.5, "average": 8.0, "n": 1}},
        "answers": [
            {
                "question": "Tell me about Python",
                "score": 8,
                "rationale": "Strong",
                "evidence_quotes": ["I use type hints"],
                "strengths": ["clear"],
                "gaps": [],
                "answer": "I use type hints and pytest",
            }
        ],
    }
    md = render_markdown(report)
    assert "Backend Engineer" in md
    assert "Lean hire" in md
    assert "type hints" in md


# --------------------------------------------------------------------------- #
# scorer schema completion (mocked LLM)
# --------------------------------------------------------------------------- #
def test_score_answer_schema_complete_on_garbage():
    comps = [{"id": "python", "name": "Python", "signals": []}]
    with patch("interview_eval.scorer.chat_json", return_value={}):
        result = score_answer("Q", "A", comps, client=object())
    assert set(result) >= {"score", "per_competency", "evidence_quotes", "strengths", "gaps", "rationale"}
    assert result["per_competency"] == {}


def test_score_answer_clamps_and_filters_ids():
    comps = [{"id": "python", "name": "Python", "signals": []}]
    fake = {
        "score": 99,
        "per_competency": {"python": 12, "unknown": 5},
        "evidence_quotes": ["q"],
        "strengths": ["s"],
        "gaps": ["g"],
        "rationale": "ok",
    }
    with patch("interview_eval.scorer.chat_json", return_value=fake):
        result = score_answer("Q", "A", comps, client=object())
    assert result["score"] == 10  # clamped to [1,10]
    assert result["per_competency"] == {"python": 10}  # unknown id dropped


def test_clamp_score():
    assert _clamp_score(0) == 1
    assert _clamp_score(11) == 10
    assert _clamp_score("nan") is None
    assert _clamp_score(None) is None


# --------------------------------------------------------------------------- #
# question_bank matching (mocked embeddings)
# --------------------------------------------------------------------------- #
def _fake_embed_factory():
    table = {
        "What is REST?": [1.0, 0.0],
        "Design a scalable system": [0.0, 1.0],
        "tell me about rest apis": [0.95, 0.05],
    }

    def fake_embed(client, texts, model="x"):
        return [table.get(t, [0.5, 0.5]) for t in texts]

    return fake_embed


def test_question_bank_matches_nearest():
    questions = [
        Question(id="q1", question="What is REST?", competencies=["api-design"]),
        Question(id="q2", question="Design a scalable system", competencies=["system-design"]),
    ]
    with patch("interview_eval.question_bank.get_client", return_value=MagicMock()), \
         patch("interview_eval.question_bank.embed", side_effect=_fake_embed_factory()):
        bank = QuestionBank(questions, match_threshold=0.5)
        q, score = bank.match("tell me about rest apis")
    assert q is not None and q.id == "q1"
    assert score > 0.5


def test_align_question_competencies_remaps_to_jd_ids():
    # Question label "api-design" should map to JD id "python-and-api-design".
    jd = [
        {"id": "python-and-api-design", "name": "Python and API Design", "description": "Builds REST APIs"},
        {"id": "system-design", "name": "System Design", "description": "Designs scalable systems"},
    ]
    questions = [Question(id="q1", question="Q", competencies=["api-design", "system-design"])]

    def fake_embed(client, texts, model="x"):
        table = {
            "Python and API Design": [1.0, 0.0],  # name-only reference
            "System Design": [0.0, 1.0],
            "api design": [0.97, 0.05],  # humanized slug
        }
        return [table.get(t, [0.5, 0.5]) for t in texts]

    with patch("interview_eval.question_bank.get_client", return_value=MagicMock()), \
         patch("interview_eval.question_bank.embed", side_effect=fake_embed):
        mapping = align_question_competencies(questions, jd, threshold=0.3)

    assert mapping["api-design"] == "python-and-api-design"
    assert mapping["system-design"] == "system-design"  # direct id passthrough
    assert questions[0].competencies == ["python-and-api-design", "system-design"]


def test_align_question_competencies_drops_below_threshold():
    jd = [{"id": "python", "name": "Python", "description": "writes python"}]
    questions = [Question(id="q1", question="Q", competencies=["underwater-basket-weaving"])]

    def fake_embed(client, texts, model="x"):
        table = {"Python": [1.0, 0.0], "underwater basket weaving": [0.0, 1.0]}
        return [table.get(t, [0.5, 0.5]) for t in texts]

    with patch("interview_eval.question_bank.get_client", return_value=MagicMock()), \
         patch("interview_eval.question_bank.embed", side_effect=fake_embed):
        mapping = align_question_competencies(questions, jd, threshold=0.3)

    assert mapping["underwater-basket-weaving"] is None
    assert questions[0].competencies == []  # dropped → scorer falls back to full rubric


def test_question_bank_below_threshold_returns_none():
    questions = [Question(id="q1", question="What is REST?")]
    with patch("interview_eval.question_bank.get_client", return_value=MagicMock()), \
         patch("interview_eval.question_bank.embed", side_effect=_fake_embed_factory()):
        bank = QuestionBank(questions, match_threshold=0.99)
        q, _ = bank.match("completely unrelated chit chat")
    assert q is None


# --------------------------------------------------------------------------- #
# InterviewSession core flow (injected deps)
# --------------------------------------------------------------------------- #
class _FakeBank:
    def __init__(self, mapping):
        self.mapping = mapping  # text substring -> Question

    def match(self, text):
        for needle, q in self.mapping.items():
            if needle in text.lower():
                return q, 0.9
        return None, 0.0


def test_session_pairs_answer_and_scores():
    q1 = Question(id="q1", question="Tell me about REST", competencies=["api-design"])
    bank = _FakeBank({"rest": q1})
    competencies = [{"id": "api-design", "name": "API Design", "weight": 1.0, "signals": []}]

    transcribe = MagicMock(side_effect=["Tell me about REST", "REST is stateless and uses HTTP"])
    score_fn = MagicMock(return_value={
        "score": 8, "per_competency": {"api-design": 8},
        "evidence_quotes": ["stateless"], "strengths": [], "gaps": [], "rationale": "good",
    })

    session = InterviewSession(
        bank=bank, competencies=competencies, role_title="Backend",
        transcribe_fn=transcribe, score_fn=score_fn,
    )
    session.on_interviewer_utterance(b"i")   # sets active question q1
    session.on_candidate_utterance(b"c")     # buffers the answer
    report = session.finalize()              # scores buffered answer

    assert score_fn.called
    assert report["overall"] == 8.0
    assert report["answers"][0]["question_id"] == "q1"
    assert "stateless" in report["answers"][0]["evidence_quotes"]


def test_run_simulated_end_to_end(tmp_path):
    sr = 16000
    # interviewer speaks first ~0.5s, candidate answers later ~0.5s; padded with silence.
    interviewer = np.concatenate([
        np.ones(int(sr * 0.5), np.float32) * 0.5,
        np.zeros(int(sr * 2.0), np.float32),
    ])
    candidate = np.concatenate([
        np.zeros(int(sr * 1.0), np.float32),
        np.ones(int(sr * 0.5), np.float32) * 0.5,
        np.zeros(int(sr * 1.0), np.float32),
    ])
    wav_path = tmp_path / "stereo.wav"
    write_stereo_wav(str(wav_path), interviewer, candidate, sample_rate=sr)

    q1 = Question(id="q1", question="Tell me about REST", competencies=["api-design"])
    bank = _FakeBank({"rest": q1})
    competencies = [{"id": "api-design", "name": "API Design", "weight": 1.0, "signals": []}]
    transcribe = MagicMock(side_effect=["Tell me about REST", "REST is stateless"])
    score_fn = MagicMock(return_value={
        "score": 7, "per_competency": {"api-design": 7},
        "evidence_quotes": [], "strengths": [], "gaps": [], "rationale": "ok",
    })
    session = InterviewSession(
        bank=bank, competencies=competencies, transcribe_fn=transcribe, score_fn=score_fn,
    )
    report = run_simulated(session, str(wav_path))
    assert report["overall"] == 7.0
    assert len(report["answers"]) == 1


# --------------------------------------------------------------------------- #
# AI-interviewer (conduct) mode
# --------------------------------------------------------------------------- #
def test_advance_to_sets_question_and_scores_previous():
    q1 = Question(id="q1", question="First?", competencies=["c"])
    q2 = Question(id="q2", question="Second?", competencies=["c"])
    competencies = [{"id": "c", "name": "C", "weight": 1.0, "signals": []}]
    transcribe = MagicMock(return_value="some answer")
    score_fn = MagicMock(return_value={
        "score": 6, "per_competency": {"c": 6}, "evidence_quotes": [],
        "strengths": [], "gaps": [], "rationale": "",
    })
    s = InterviewSession(bank=_FakeBank({}), competencies=competencies,
                         transcribe_fn=transcribe, score_fn=score_fn)
    s.advance_to(q1)
    s.on_candidate_utterance(b"a")           # answer to q1
    s.advance_to(q2)                          # should score q1's answer
    assert score_fn.call_count == 1
    assert s.active_question.id == "q2"
    assert s.answers[0]["question_id"] == "q1"


def test_add_followup_recorded_in_entry():
    q1 = Question(id="q1", question="First?", competencies=["c"])
    competencies = [{"id": "c", "name": "C", "weight": 1.0, "signals": []}]
    transcribe = MagicMock(return_value="answer text")
    score_fn = MagicMock(return_value={
        "score": 7, "per_competency": {"c": 7}, "evidence_quotes": [],
        "strengths": [], "gaps": [], "rationale": "",
    })
    s = InterviewSession(bank=_FakeBank({}), competencies=competencies,
                         transcribe_fn=transcribe, score_fn=score_fn)
    s.advance_to(q1)
    s.on_candidate_utterance(b"a")
    s.add_followup("Can you give an example?")
    report = s.finalize()
    assert report["answers"][0]["followups"] == ["Can you give an example?"]


def test_generate_followup_returns_text():
    from interview_eval.dialogue import generate_followup
    with patch("interview_eval.dialogue.chat_text", return_value="What was the impact?"):
        fu = generate_followup("Tell me about X", "It was hard", client=object())
    assert fu == "What was the impact?"


def test_speaker_falls_back_to_print_on_error(capsys):
    from interview_eval.tts import Speaker
    spk = Speaker(device="nonexistent-device", engine="openai", api_key="k")
    with patch("interview_eval.tts.synth_openai", side_effect=RuntimeError("no net")):
        spk("Hello candidate")
    out = capsys.readouterr().out
    assert "AI would say: Hello candidate" in out


def test_play_array_default_device_when_none(monkeypatch):
    # --dry-run uses device=None → must play to the system default (no resolution).
    import interview_eval.tts as tts
    fake_sd = MagicMock()
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    tts.play_array(np.zeros(10, dtype=np.int16), 24000, None)
    assert fake_sd.play.call_args.kwargs["device"] is None
    fake_sd.wait.assert_called_once()


def test_run_conduct_drives_questions_and_scores(monkeypatch):
    # Drive the keyboard loop deterministically: begin, advance, advance, then EOF.
    q1 = Question(id="q1", question="First?", competencies=["c"])
    q2 = Question(id="q2", question="Second?", competencies=["c"])
    competencies = [{"id": "c", "name": "C", "weight": 1.0, "signals": []}]
    transcribe = MagicMock(return_value="an answer")
    score_fn = MagicMock(return_value={
        "score": 8, "per_competency": {"c": 8}, "evidence_quotes": [],
        "strengths": [], "gaps": [], "rationale": "",
    })
    session = InterviewSession(bank=_FakeBank({}), competencies=competencies,
                               transcribe_fn=transcribe, score_fn=score_fn)

    spoken = []
    state = {"calls": 0}

    def fake_prompt(_):
        # Call 1 = "begin"; calls 2 & 3 = the per-question control prompts.
        # Simulate the candidate having answered before each advance.
        state["calls"] += 1
        if state["calls"] >= 2:
            session.on_candidate_utterance(b"audio")
        return ""

    # Stub the audio stack so no hardware is touched.
    class _DummyStream:
        def start(self): pass
        def stop(self): pass
        def close(self): pass

    monkeypatch.setattr("interview_eval.session.open_input_stream", lambda *a, **k: _DummyStream())

    report = run_conduct(
        session, questions=[q1, q2], speak=lambda t: spoken.append(t),
        input_device="dummy", prompt_fn=fake_prompt,
    )
    assert spoken == ["First?", "Second?"]   # both questions voiced
    assert len(report["answers"]) == 2       # both scored at end


def test_freeform_anchors_on_spoken_questions(monkeypatch):
    # No bank: each substantial interviewer turn becomes the active question and
    # the candidate's answer is scored against the full JD rubric.
    competencies = [{"id": "c", "name": "C", "weight": 1.0, "signals": []}]
    transcribe = MagicMock(side_effect=[
        "Tell me about your experience with Python",  # interviewer Q1 (substantial)
        "I have used Python for five years building APIs",  # candidate answer
        "Walk me through a hard bug you fixed recently",  # interviewer Q2
        "I traced a memory leak using profiling tools",  # candidate answer
    ])
    score_fn = MagicMock(return_value={
        "score": 8, "per_competency": {"c": 8}, "evidence_quotes": [],
        "strengths": [], "gaps": [], "rationale": "",
    })
    s = InterviewSession(bank=None, competencies=competencies, freeform=True,
                         transcribe_fn=transcribe, score_fn=score_fn)
    s.on_interviewer_utterance(b"q1")   # sets Q1
    s.on_candidate_utterance(b"a1")
    s.on_interviewer_utterance(b"q2")   # scores Q1, sets Q2
    s.on_candidate_utterance(b"a2")
    report = s.finalize()               # scores Q2

    assert len(report["answers"]) == 2
    assert report["answers"][0]["question"] == "Tell me about your experience with Python"
    assert report["answers"][0]["answer"] == "I have used Python for five years building APIs"
    assert report["answers"][1]["question"] == "Walk me through a hard bug you fixed recently"


def test_freeform_ignores_backchannels():
    competencies = [{"id": "c", "name": "C", "weight": 1.0, "signals": []}]
    transcribe = MagicMock(side_effect=[
        "Tell me about your experience with Python",  # Q1
        "right",            # short backchannel → NOT a new question
        "okay got it",      # multi-word backchannel → NOT a new question
    ])
    score_fn = MagicMock(return_value={
        "score": 7, "per_competency": {"c": 7}, "evidence_quotes": [],
        "strengths": [], "gaps": [], "rationale": "",
    })
    s = InterviewSession(bank=None, competencies=competencies, freeform=True,
                         transcribe_fn=transcribe, score_fn=score_fn)
    s.on_interviewer_utterance(b"q1")
    s.on_interviewer_utterance(b"back1")  # "right"
    s.on_interviewer_utterance(b"back2")  # "okay got it"
    assert s.active_question.question == "Tell me about your experience with Python"
    assert s._freeform_qn == 1  # only one question created


def test_run_conduct_is_echo_safe_and_captures_answer(monkeypatch):
    # Regression: the AI's spoken question must NOT be captured as the answer,
    # and the candidate's answer must be the bounded span before Enter.
    q1 = Question(id="q1", question="First?", competencies=["c"])
    competencies = [{"id": "c", "name": "C", "weight": 1.0, "signals": []}]
    transcribe = MagicMock(return_value="real candidate answer")
    score_fn = MagicMock(return_value={
        "score": 7, "per_competency": {"c": 7}, "evidence_quotes": [],
        "strengths": [], "gaps": [], "rationale": "",
    })
    session = InterviewSession(bank=_FakeBank({}), competencies=competencies,
                               transcribe_fn=transcribe, score_fn=score_fn)

    holder = {}

    class _Stream:
        def start(self): pass
        def stop(self): pass
        def close(self): pass

    def fake_open(device, channels, callback, **k):
        holder["cb"] = callback
        return _Stream()

    monkeypatch.setattr("interview_eval.session.open_input_stream", fake_open)
    loud = np.ones((100, 1), dtype=np.float32) * 0.5

    def fake_speak(_text):
        # Simulate the AI voice leaking into the mic while it's speaking.
        holder["cb"](loud, 100, None, None)

    state = {"n": 0}

    def fake_prompt(_):
        state["n"] += 1
        if state["n"] == 2:  # control prompt for q1 → candidate speaks
            holder["cb"](loud, 100, None, None)
        return ""

    report = run_conduct(session, questions=[q1], speak=fake_speak,
                         input_device=None, prompt_fn=fake_prompt)
    assert transcribe.call_count == 1                       # echo dropped, not transcribed
    assert len(report["answers"]) == 1
    assert report["answers"][0]["answer"] == "real candidate answer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
