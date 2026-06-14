#!/usr/bin/env python
"""CLI entrypoint for hire-eval: live interview evaluation.

Subcommands:
    list-devices            List input audio devices (find your Aggregate Device)
    check-audio --device D  Record briefly; print per-channel RMS to verify routing
    run --jd --questions    Run a live interview and generate a scored report
    simulate --wav stereo   Replay a stereo WAV through the full pipeline (offline)

Environment:
    OPENAI_API_KEY (env, .env, --api-key, or OS keyring).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    import keyring
except Exception:  # keyring is optional
    keyring = None

_CONSENT = (
    "⚠  Recording/transcribing an interview may require the candidate's consent "
    "(and may be legally required where you are). Make sure they've agreed."
)


# --------------------------------------------------------------------------- #
# API key resolution (mirrors lazy_prompt.cli; service name "hire-eval")
# --------------------------------------------------------------------------- #
def _get_api_key(arg_key: str | None) -> str | None:
    if arg_key:
        return arg_key
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key
    if keyring:
        try:
            return keyring.get_password("hire-eval", "OPENAI_API_KEY")
        except Exception:
            return None
    return None


def _persist_api_key(api_key: str | None) -> None:
    if not api_key or not keyring:
        return
    try:
        keyring.set_password("hire-eval", "OPENAI_API_KEY", api_key)
    except Exception:
        pass


def _ensure_key(args) -> str | None:
    load_dotenv()
    key = _get_api_key(getattr(args, "api_key", None))
    if not key:
        print("Missing OPENAI_API_KEY. Pass --api-key once, or set env/.env/Keychain.")
        return None
    os.environ["OPENAI_API_KEY"] = key
    _persist_api_key(getattr(args, "api_key", None))
    return key


# --------------------------------------------------------------------------- #
# Subcommand handlers
# --------------------------------------------------------------------------- #
def _cmd_list_devices(args) -> int:
    """List all available input and output audio devices.

    Args:
        args: CLI arguments (not used here).

    Returns:
        0 on success.
    """
    from .audio_router import list_input_devices, list_output_devices

    inputs = list_input_devices()
    print("Input devices (for capturing the candidate):")
    for d in inputs:
        print(f"  [{d.index:>2}] {d.name}  ({d.max_input_channels} ch, {int(d.default_samplerate)} Hz)")
    print("\nOutput devices (for AI voice → Meet mic in `conduct`):")
    for d in list_output_devices():
        print(f"  [{d.index:>2}] {d.name}  ({d.max_input_channels} ch, {int(d.default_samplerate)} Hz)")
    print("\nTips:")
    print("  • `run`     → input = Aggregate Device (your mic + BlackHole)")
    print("  • `conduct` → input = BlackHole tapping Meet output; output = BlackHole set as Meet's mic")
    return 0


def _cmd_check_audio(args) -> int:
    """Verify audio routing by recording and printing per-channel RMS levels.

    Args:
        args: CLI arguments containing device and duration.

    Returns:
        0 on success, 1 on failure.
    """
    from .audio_router import channel_rms

    print(f"Recording {args.seconds:.0f}s from '{args.device}'. "
          "Speak, and play some audio through Meet/your speakers…")
    try:
        rms = channel_rms(args.device, seconds=args.seconds)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1
    print("\nPer-channel RMS (look for one channel responding to YOUR voice, "
          "another to the candidate/Meet playback):")
    for i, r in enumerate(rms):
        bar = "█" * min(int(r * 200), 40)
        print(f"  ch{i}: {r:.4f} {bar}")
    if len(rms) < 2:
        print("\n⚠  Only one channel — this device can't separate speakers. "
              "Create an Aggregate Device (Built-in Mic + BlackHole 2ch).")
    return 0


def _build_session(args, key):
    from .jd_parser import load_or_parse
    from .question_bank import QuestionBank, align_question_competencies, load_questions
    from .session import InterviewSession

    parsed = load_or_parse(
        args.jd, args.competencies_cache, force=args.reparse_jd, api_key=key
    )
    competencies = parsed.get("competencies", [])
    role_title = parsed.get("role_title", "")
    print(f"Role: {role_title or '(untitled)'} — {len(competencies)} competencies")
    for c in competencies:
        print(f"  • {c['name']}  ({c['weight'] * 100:.0f}%)")

    # Freeform when no question bank is supplied: your spoken questions anchor
    # scoring, and answers are judged against the full JD rubric.
    freeform = not getattr(args, "questions", None)
    if freeform:
        print("\n🎙  Freeform mode: no question bank. Ask naturally — each spoken "
              "question anchors the next answer, scored against the full JD rubric.")
        return InterviewSession(
            bank=None,
            competencies=competencies,
            role_title=role_title,
            candidate_name=args.candidate or "",
            api_key=key,
            language=args.language,
            freeform=True,
        )

    questions = load_questions(args.questions)
    print(f"Loaded {len(questions)} interview questions. Aligning competencies…")
    mapping = align_question_competencies(questions, competencies, api_key=key)
    for label, target in mapping.items():
        if target == label:
            continue
        if target is None:
            print(f"  ⚠  question competency '{label}' → no JD match (full rubric will apply)")
        else:
            print(f"  ↪  '{label}' → '{target}'")

    print("Embedding questions…")
    bank = QuestionBank(questions, api_key=key)

    return InterviewSession(
        bank=bank,
        competencies=competencies,
        role_title=role_title,
        candidate_name=args.candidate or "",
        api_key=key,
        language=args.language,
    )


def _cmd_run(args) -> int:
    """Execute a live interview capture and generate a scored report.

    Args:
        args: CLI arguments for JD, device, and output.

    Returns:
        0 on success, 1 on error.
    """
    key = _ensure_key(args)
    if not key:
        return 1
    print(_CONSENT + "\n")
    from .session import run_live
    from .display import render

    session = _build_session(args, key)
    print("\nStarting live interview. Ask your questions naturally; Ctrl+C to finish.\n")
    report = run_live(
        session,
        device=args.device,
        interviewer_channel=args.interviewer_channel,
        candidate_channel=args.candidate_channel,
        render_fn=render,
    )
    return _emit_report(report, args.output_dir)


def _cmd_simulate(args) -> int:
    """Replay a stereo WAV file to test the pipeline without a live microphone.

    Args:
        args: CLI arguments containing the WAV path.

    Returns:
        0 on success, 1 on error.
    """
    key = _ensure_key(args)
    if not key:
        return 1
    print(_CONSENT + "\n")
    from .session import run_simulated

    session = _build_session(args, key)
    print(f"\nReplaying {args.wav} through the pipeline…\n")
    report = run_simulated(session, args.wav)
    return _emit_report(report, args.output_dir)


def _cmd_conduct(args) -> int:
    """Run the AI-interviewer mode where AI voices the questions and probes gaps.

    Args:
        args: CLI arguments for audio routing and TTS preferences.

    Returns:
        0 on success, 1 on error.
    """
    key = _ensure_key(args)
    if not key:
        return 1
    if not args.questions:
        print("Error: conduct mode needs --questions (the AI reads them aloud). "
              "Freeform applies to `run`/`simulate`, where you ask the questions.")
        return 1
    print(_CONSENT + "\n")
    from .dialogue import generate_followup
    from .session import run_conduct
    from .tts import Speaker

    input_device = args.input_device
    output_device = args.output_device
    if args.dry_run:
        # Rehearse locally: AI voice → default speakers, "candidate" = your mic.
        input_device = args.input_device  # None unless explicitly given
        output_device = args.output_device
        print("🧪 Dry run: AI voice plays to your default speakers and captures "
              "your default mic as the 'candidate'. Use headphones to avoid echo.\n")
    elif not (input_device and output_device):
        print("Error: --input-device and --output-device are required for a live "
              "interview (or pass --dry-run to rehearse locally). See docs/AUDIO_SETUP.md.")
        return 1

    session = _build_session(args, key)
    speaker = Speaker(
        device=output_device, engine=args.engine, voice=args.voice, api_key=key
    )

    # Print candidate speech and scores as they happen (capture runs in a thread).
    def on_event(ev):
        if ev["type"] == "candidate":
            print(f"   🎤 {ev['text']}")
        elif ev["type"] == "score":
            e = ev["entry"]
            print(f"   ✓ scored {e['question_id']}: {e.get('score')}/10")

    session.on_event = on_event

    def followup_fn(question, answer):
        return generate_followup(question, answer, role_title=session.role_title, api_key=key)

    print("\n🎙  AI-interviewer mode. The AI will voice questions to the candidate.\n")
    report = run_conduct(
        session,
        questions=session.bank.questions,
        speak=speaker,
        input_device=input_device,
        candidate_channel=args.candidate_channel,
        followup_fn=followup_fn if args.followups else None,
    )
    return _emit_report(report, args.output_dir)


def _emit_report(report, output_dir: str) -> int:
    from .report import render_markdown, save_report

    print("\n" + render_markdown(report) + "\n")
    out_dir = save_report(report, output_dir)
    print(f"✓ Report saved to: {out_dir}")
    return 0


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #
def _add_common_eval_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--jd", required=True, help="Path to the job description text file")
    p.add_argument("--questions", help="Path to questions.yaml (omit in run/simulate for freeform mode)")
    p.add_argument(
        "--competencies-cache",
        default="competencies.json",
        help="Cache file for parsed JD competencies (default: competencies.json)",
    )
    p.add_argument("--reparse-jd", action="store_true", help="Re-parse the JD, ignoring cache")
    p.add_argument("--candidate", default="", help="Candidate name (for the report)")
    p.add_argument("--language", default="en", help="Spoken language code (default: en)")
    p.add_argument(
        "--output-dir",
        default=str(Path.home() / "hire-eval"),
        help="Where to write reports (default: ~/hire-eval)",
    )
    p.add_argument("--api-key", help="OPENAI_API_KEY (persisted to OS keyring if available)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live interview evaluation (Whisper + GPT-4o)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-devices", help="List input audio devices")
    p_list.set_defaults(func=_cmd_list_devices)

    p_check = sub.add_parser("check-audio", help="Verify per-channel audio routing")
    p_check.add_argument("--device", required=True, help="Device name or index")
    p_check.add_argument("--seconds", type=float, default=5.0)
    p_check.set_defaults(func=_cmd_check_audio)

    p_run = sub.add_parser("run", help="Run a live interview")
    _add_common_eval_args(p_run)
    p_run.add_argument("--device", required=True, help="Aggregate Device name or index")
    p_run.add_argument("--interviewer-channel", type=int, default=0)
    p_run.add_argument("--candidate-channel", type=int, default=1)
    p_run.set_defaults(func=_cmd_run)

    p_sim = sub.add_parser("simulate", help="Replay a stereo WAV through the pipeline (offline)")
    _add_common_eval_args(p_sim)
    p_sim.add_argument("--wav", required=True, help="Stereo WAV (ch0=interviewer, ch1=candidate)")
    p_sim.set_defaults(func=_cmd_simulate)

    p_con = sub.add_parser("conduct", help="AI voices the questions to the candidate (human-paced)")
    _add_common_eval_args(p_con)
    p_con.add_argument("--input-device", help="Device capturing the candidate (BlackHole tapping Meet output); omit with --dry-run")
    p_con.add_argument("--output-device", help="Device set as Meet's mic (AI voice is played here); omit with --dry-run")
    p_con.add_argument("--dry-run", action="store_true", help="Rehearse locally: AI voice → your speakers, your mic = candidate (no BlackHole needed)")
    p_con.add_argument("--candidate-channel", type=int, default=0)
    p_con.add_argument("--engine", choices=["openai", "say"], default="openai", help="TTS engine (default: openai tts-1)")
    p_con.add_argument("--voice", default="nova", help="OpenAI TTS voice (default: nova)")
    p_con.add_argument("--no-followups", dest="followups", action="store_false", help="Disable AI adaptive follow-ups (bank only)")
    p_con.set_defaults(func=_cmd_conduct, followups=True)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
