"""Unit tests for meet-mom: all pure/mocked — no audio, no API, no network."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from meeting_mom.meeting import Meeting, Participant, build_meeting, load_agenda, parse_participants
from meeting_mom.mom import (
    MOM_SCHEMA_KEYS,
    generate_mom,
    render_html,
    render_markdown,
    _normalize,
    _system_prompt,
)
from meeting_mom.session import MeetingSession, _fmt_ts, run_simulated
from meeting_mom.share import build_email_draft, save_bundle, write_email_draft


# --------------------------------------------------------------------------- #
# meeting.py
# --------------------------------------------------------------------------- #
def test_parse_participants_name_role_email():
    ps = parse_participants("You (Host); Jane Doe (Acme, VP Product) <jane@acme.com>; Bob Lee")
    assert [p.name for p in ps] == ["You", "Jane Doe", "Bob Lee"]
    assert ps[1].role == "Acme, VP Product"
    assert ps[1].email == "jane@acme.com"
    assert ps[2].role == "" and ps[2].email is None


def test_parse_participants_ignores_blanks():
    assert parse_participants("  ; ; ") == []


def test_meeting_defaults_datetime_and_slug():
    m = Meeting(title="Acme Q3 Roadmap Review!")
    assert m.datetime_iso  # auto-filled
    assert m.slug() == "acme-q3-roadmap-review"


def test_meeting_recipient_emails_filters_none():
    m = Meeting(participants=[Participant("A", email="a@x.com"), Participant("B")])
    assert m.recipient_emails() == ["a@x.com"]


def test_load_agenda_strips_bullets(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("- Intro\n* Budget\n\n  Timeline  \n")
    assert load_agenda(str(f)) == ["Intro", "Budget", "Timeline"]
    assert load_agenda(None) == []


def test_build_meeting_end_to_end(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("Item one\nItem two\n")
    m = build_meeting(title="Sync", participants_spec="A <a@x.com>", agenda_path=str(f), host_name="Mohit")
    assert m.title == "Sync"
    assert m.agenda == ["Item one", "Item two"]
    assert m.host_name == "Mohit"
    assert m.recipient_emails() == ["a@x.com"]


# --------------------------------------------------------------------------- #
# mom.py — normalize + render (deterministic, no LLM)
# --------------------------------------------------------------------------- #
def _sample_mom():
    return {
        "meetingTitle": "Acme Q3 Roadmap",
        "dateTime": "2026-06-11T10:00:00",
        "participants": ["You (Host)", "Jane Doe (Acme)"],
        "agenda": ["Roadmap", "Budget"],
        "discussion": [{"topic": "Roadmap", "points": ["Ship A in Q3", "Defer B"]}],
        "decisions": ["Approve phase 1"],
        "actionItems": [{"task": "Send SOW", "owner": "Host", "dueDate": "2026-06-18", "priority": "High"}],
        "risks": ["Timeline tight"],
        "dependencies": ["Legal sign-off"],
        "openQuestions": ["Final budget?"],
        "nextSteps": ["Schedule follow-up"],
        "summary": ["Productive roadmap review."],
    }


def test_system_prompt_excludes_small_talk():
    sp = _system_prompt().lower()
    assert "exclude" in sp
    # work-only: small talk / off-topic must be explicitly excluded
    for term in ["greeting", "small talk", "off-topic", "family", "work-related"]:
        assert term in sp


def test_normalize_fills_missing_keys():
    out = _normalize({}, Meeting(title="T"))
    assert MOM_SCHEMA_KEYS <= set(out)
    assert out["platform"] == "Google Meet"
    assert out["meetingTitle"] == "T"
    assert isinstance(out["actionItems"], list)


def test_normalize_coerces_wrong_types():
    out = _normalize({"decisions": "not a list", "meetingTitle": 5}, Meeting(title="X"))
    assert out["decisions"] == []
    assert out["meetingTitle"] == "X"  # fell back to meeting title


def test_render_markdown_contains_sections_and_action_table():
    md = render_markdown(_sample_mom(), prepared_by="Mohit")
    for heading in ["# Minutes of Meeting", "## Executive Summary", "## Action Items", "## Next Steps"]:
        assert heading in md
    assert "Send SOW" in md and "| 1 |" in md  # action item rendered as table row
    assert "Prepared by:** Mohit" in md


def test_render_html_escapes_and_has_table():
    mom = _sample_mom()
    mom["meetingTitle"] = "A & B <test>"
    html = render_html(mom)
    assert "A &amp; B &lt;test&gt;" in html  # escaped
    assert "<table" in html and "Send SOW" in html


def _mock_client_returning(payload: dict) -> MagicMock:
    """An OpenAI-shaped mock whose chat completion returns ``payload`` as JSON."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = json.dumps(payload)
    client = MagicMock()
    client.chat.completions.create.return_value = resp
    return client


def test_generate_mom_parses_and_normalizes():
    """generate_mom: prompt → (mocked) API → JSON parse → schema-complete normalize."""
    payload = {
        "meetingTitle": "Acme Sync",
        "decisions": ["Approve phase 1"],
        "actionItems": [{"task": "Send SOW", "owner": "Host"}],
        "summary": ["Productive call"],
    }
    meeting = Meeting(title="Fallback Title")
    client = _mock_client_returning(payload)

    out = generate_mom("[00:00:01] Host: hello", meeting, client=client)

    # Model-provided fields survive.
    assert out["meetingTitle"] == "Acme Sync"
    assert out["decisions"] == ["Approve phase 1"]
    # Every schema key is present and correctly typed after normalization.
    assert MOM_SCHEMA_KEYS <= set(out)
    assert isinstance(out["risks"], list) and out["risks"] == []
    assert out["platform"] == "Google Meet"
    # Missing dateTime/participants fall back to the meeting metadata.
    assert out["dateTime"] == meeting.datetime_iso
    # The request actually went through the JSON-mode chat path.
    assert client.chat.completions.create.called


def test_generate_mom_recovers_from_unparseable_response():
    """A non-JSON model reply degrades to a schema-complete empty MoM, not a crash."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = "sorry, I can't do that"
    client = MagicMock()
    client.chat.completions.create.return_value = resp

    meeting = Meeting(title="Recovery Test")
    out = generate_mom("[00:00:01] Host: hi", meeting, client=client)

    assert MOM_SCHEMA_KEYS <= set(out)
    assert out["meetingTitle"] == "Recovery Test"  # fell back to meeting title
    assert out["decisions"] == []


# --------------------------------------------------------------------------- #
# session.py — transcript building (mock transcribe + mom)
# --------------------------------------------------------------------------- #
def test_fmt_ts():
    assert _fmt_ts(0) == "00:00:00"
    assert _fmt_ts(3725) == "01:02:05"
    assert _fmt_ts(-5) == "00:00:00"


def test_session_builds_labeled_transcript():
    seen = {}

    def fake_transcribe(wav: bytes) -> str:
        return wav.decode()

    def fake_mom(text: str, meeting: Meeting):
        seen["text"] = text
        return _normalize({}, meeting)

    s = MeetingSession(Meeting(title="T"), transcribe_fn=fake_transcribe, mom_fn=fake_mom)
    s._elapsed_override = 12.0
    s.on_host_utterance(b"hello there")
    s._elapsed_override = 75.0
    s.on_client_utterance(b"hi back")
    s.on_host_utterance(b"   ")  # whitespace-only → dropped

    assert s.transcript_text() == "[00:00:12] Host: hello there\n[00:01:15] Client: hi back"
    s.finalize()
    assert "Host: hello there" in seen["text"] and "Client: hi back" in seen["text"]


def test_session_emits_events():
    events = []
    s = MeetingSession(
        Meeting(title="T"),
        transcribe_fn=lambda w: "x",
        mom_fn=lambda t, m: {},
        on_event=events.append,
    )
    s.on_host_utterance(b"x")
    assert events[0]["type"] == "utterance" and events[0]["speaker"] == "Host"


def test_run_simulated_with_synth_wav(tmp_path):
    """End-to-end offline driver over a real stereo WAV, OpenAI fully mocked."""
    import numpy as np
    from interview_eval.audio_router import write_stereo_wav

    sr = 16000
    silence = np.zeros(sr, np.float32)
    tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)).astype(np.float32)
    host = np.concatenate([tone, silence, silence])      # host speaks first second
    client = np.concatenate([silence, silence, tone])    # client speaks third second
    wav = tmp_path / "t.wav"
    write_stereo_wav(str(wav), host, client, sample_rate=sr)

    calls = {"n": 0}

    def fake_transcribe(_wav: bytes) -> str:
        calls["n"] += 1
        return f"utterance {calls['n']}"

    captured = {}

    def fake_mom(text: str, meeting: Meeting):
        captured["text"] = text
        return _normalize({"summary": ["ok"]}, meeting)

    s = MeetingSession(Meeting(title="Sim"), transcribe_fn=fake_transcribe, mom_fn=fake_mom)
    mom = run_simulated(s, str(wav))
    # Both speakers should have produced at least one utterance.
    assert "Host:" in captured["text"] and "Client:" in captured["text"]
    assert mom["summary"] == ["ok"]


# --------------------------------------------------------------------------- #
# share.py — bundle + email draft (no network)
# --------------------------------------------------------------------------- #
def test_save_bundle_writes_all_files(tmp_path):
    m = Meeting(title="Acme Sync", participants=[Participant("Jane", email="j@a.com")])
    bundle = save_bundle(_sample_mom(), m, "transcript here", str(tmp_path), prepared_by="Mohit")
    import os

    files = set(os.listdir(bundle.directory))
    assert {"transcript.txt", "mom.json", "mom.md", "mom.html", "meeting.json"} <= files
    with open(os.path.join(bundle.directory, "mom.json")) as f:
        assert json.load(f)["meetingTitle"] == "Acme Q3 Roadmap"
    assert "# Minutes of Meeting" in bundle.markdown


def test_build_email_draft_recipients_and_subject(tmp_path):
    m = Meeting(
        title="Acme Sync",
        datetime_iso="2026-06-11T10:00:00",
        participants=[Participant("Jane", email="jane@acme.com"), Participant("Bob")],
    )
    bundle = save_bundle(_sample_mom(), m, "t", str(tmp_path))
    draft = build_email_draft(_sample_mom(), m, bundle, extra_recipients=["cc@x.com", "jane@acme.com"])
    assert draft.to == ["jane@acme.com", "cc@x.com"]  # deduped, participant first
    assert draft.subject == "Minutes of Meeting — Acme Q3 Roadmap (2026-06-11)"
    assert "<table" in draft.html_body


def test_write_email_draft_persists_spec(tmp_path):
    m = Meeting(title="Acme Sync", participants=[Participant("Jane", email="jane@acme.com")])
    bundle = save_bundle(_sample_mom(), m, "t", str(tmp_path))
    draft = build_email_draft(_sample_mom(), m, bundle)
    path = write_email_draft(draft, bundle.directory)
    with open(path) as f:
        spec = json.load(f)
    assert spec["to"] == ["jane@acme.com"]
    assert spec["subject"].startswith("Minutes of Meeting — Acme Q3 Roadmap")
    assert "<table" in spec["html_body"]

def test_generate_mom_success():
    from meeting_mom.mom import generate_mom
    from unittest.mock import patch, MagicMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"meetingTitle": "Test Meeting", "summary": ["Success"]}'
    mock_client.chat.completions.create.return_value = mock_response

    m = Meeting(title="Real Title")
    res = generate_mom("Transcript text", m, client=mock_client)

    assert res["meetingTitle"] == "Test Meeting"
    assert res["summary"] == ["Success"]
    assert res["platform"] == "Google Meet"

def test_generate_mom_malformed_json():
    from meeting_mom.mom import generate_mom
    from unittest.mock import patch, MagicMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = 'This is not JSON'
    mock_client.chat.completions.create.return_value = mock_response

    m = Meeting(title="Real Title")
    res = generate_mom("Transcript text", m, client=mock_client)

    # Should fall back to normalization and use meeting title
    assert res["meetingTitle"] == "Real Title"
    assert res["summary"] == []
