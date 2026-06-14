#!/usr/bin/env python
"""CLI entrypoint for meet-mom: client-meeting minutes from Google Meet.

Subcommands:
    list-devices              List input audio devices (find your Aggregate Device)
    check-audio --device D    Record briefly; print per-channel RMS to verify routing
    record --device D ...     Capture a live meeting and generate a MoM
    simulate --wav stereo     Replay a stereo WAV through the pipeline (offline)
    from-transcript --file F  Generate a MoM from an existing transcript (no audio)

Audio routing is identical to `hire-eval run` (Meet Speaker = your Multi-Output
device, headphones on). Channel 0 = Host (you), channel 1 = Client side.

Environment:
    OPENAI_API_KEY (env, .env, --api-key, or OS keyring under service "meet-mom").
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

from .meeting import build_meeting
from .mom import DEFAULT_MOM_MODEL

_CONSENT = (
    "⚠  Recording/transcribing a client meeting may require all participants' "
    "consent (and may be legally required where you are). Make sure they've agreed."
)


# --------------------------------------------------------------------------- #
# API key resolution (mirrors interview_eval.cli; service name "meet-mom")
# --------------------------------------------------------------------------- #
def _get_api_key(arg_key: str | None) -> str | None:
    if arg_key:
        return arg_key
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENAI_API_KEY")
    if keyring:
        try:
            return keyring.get_password("meet-mom", "OPENAI_API_KEY")
        except Exception:
            return None
    return None


def _ensure_key(args) -> str | None:
    load_dotenv()
    key = _get_api_key(getattr(args, "api_key", None))
    if not key:
        print("Missing OPENAI_API_KEY. Pass --api-key once, or set env/.env/Keychain.")
        return None
    os.environ["OPENAI_API_KEY"] = key
    if getattr(args, "api_key", None) and keyring:
        try:
            keyring.set_password("meet-mom", "OPENAI_API_KEY", args.api_key)
        except Exception:
            pass
    return key


# --------------------------------------------------------------------------- #
# Device subcommands — thin re-exports of the shared audio engine
# --------------------------------------------------------------------------- #
def _cmd_list_devices(args) -> int:
    from interview_eval.audio_router import list_input_devices, list_output_devices

    print("Input devices (capture: ch0=Host mic, ch1=Client via BlackHole):")
    for d in list_input_devices():
        print(f"  [{d.index:>2}] {d.name}  ({d.max_input_channels} ch, {int(d.default_samplerate)} Hz)")
    print("\nOutput devices (set Meet's Speaker to your Multi-Output device):")
    for d in list_output_devices():
        print(f"  [{d.index:>2}] {d.name}  ({d.max_input_channels} ch, {int(d.default_samplerate)} Hz)")
    print("\nTip: use the SAME Aggregate Device as `hire-eval` "
          "(your mic + BlackHole). Meet Speaker = your Multi-Output device.")
    return 0


def _cmd_check_audio(args) -> int:
    from interview_eval.audio_router import channel_rms

    print(f"Recording {args.seconds:.0f}s from '{args.device}'. "
          "Speak (Host=ch0), and play Meet/other-side audio (Client=ch1)…")
    try:
        rms = channel_rms(args.device, seconds=args.seconds)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1
    print("\nPer-channel RMS (ch0 should respond to YOU, ch1 to the other side):")
    for i, r in enumerate(rms):
        bar = "█" * min(int(r * 200), 40)
        print(f"  ch{i}: {r:.4f} {bar}")
    if len(rms) < 2:
        print("\n⚠  Only one channel — can't separate Host/Client. Use the "
              "Aggregate Device (mic + BlackHole 2ch).")
    return 0


# --------------------------------------------------------------------------- #
# MoM subcommands
# --------------------------------------------------------------------------- #
def _meeting_from_args(args):
    return build_meeting(
        title=args.title,
        datetime_iso=getattr(args, "datetime", "") or "",
        participants_spec=getattr(args, "participants", "") or "",
        agenda_path=getattr(args, "agenda", None),
        host_name=getattr(args, "host_name", "Host") or "Host",
    )


def _cmd_record(args) -> int:
    key = _ensure_key(args)
    if not key:
        return 1
    print(_CONSENT + "\n")
    from .session import MeetingSession, run_live
    from .display import render

    meeting = _meeting_from_args(args)
    session = MeetingSession(meeting, language=args.language, model=args.model, api_key=key)
    print(f"Meeting: {meeting.title or '(untitled)'} — "
          f"{len(meeting.participants)} attendees. Model: {args.model}")
    print("\nStarting live capture. Speak naturally; Ctrl+C to finish.\n")
    mom = run_live(
        session,
        device=args.device,
        host_channel=args.host_channel,
        client_channel=args.client_channel,
        render_fn=render,
    )
    return _finish(args, meeting, session.transcript_text(), mom)


def _cmd_simulate(args) -> int:
    key = _ensure_key(args)
    if not key:
        return 1
    print(_CONSENT + "\n")
    from .session import MeetingSession, run_simulated

    meeting = _meeting_from_args(args)
    session = MeetingSession(meeting, language=args.language, model=args.model, api_key=key)
    print(f"\nReplaying {args.wav} through the pipeline…\n")
    mom = run_simulated(session, args.wav)
    return _finish(args, meeting, session.transcript_text(), mom)


def _cmd_from_transcript(args) -> int:
    key = _ensure_key(args)
    if not key:
        return 1
    from .mom import generate_mom

    meeting = _meeting_from_args(args)
    transcript_text = Path(args.file).read_text(encoding="utf-8")
    print(f"\nGenerating minutes from {args.file} ({len(transcript_text)} chars)…\n")
    mom = generate_mom(transcript_text, meeting, model=args.model)
    return _finish(args, meeting, transcript_text, mom)


# --------------------------------------------------------------------------- #
# Shared finish: render, save, clipboard, optional Gmail draft
# --------------------------------------------------------------------------- #
def _finish(args, meeting, transcript_text, mom) -> int:
    from .share import build_email_draft, copy_to_clipboard, save_bundle, write_email_draft

    prepared_by = meeting.host_name if meeting.host_name != "Host" else ""
    bundle = save_bundle(
        mom, meeting, transcript_text, args.output_dir, prepared_by=prepared_by
    )
    print("\n" + bundle.markdown + "\n")
    print(f"✓ Saved: {bundle.directory}")

    if not getattr(args, "no_clipboard", False):
        if copy_to_clipboard(bundle.markdown):
            print("✓ MoM copied to clipboard")

    if getattr(args, "email_draft", False):
        draft = build_email_draft(mom, meeting, bundle, extra_recipients=_split(args.cc))
        draft_path = write_email_draft(draft, bundle.directory)
        _emit_email_draft(draft, draft_path)
    return 0


def _emit_email_draft(draft, draft_path: str) -> None:
    """Surface the email-draft spec; the actual Gmail draft is created from the file.

    meet-mom never sends mail and never calls the Gmail integration directly — it
    writes a draft spec (recipients/subject/HTML body) to ``email_draft.json`` in
    the bundle. Create the real Gmail draft from it via Claude (Gmail integration)
    or any Gmail-API client. The HTML body is also saved as ``mom.html``.
    """
    print("\n── Email draft prepared (review before sending) ────────────────")
    print(f"To:      {', '.join(draft.to) if draft.to else '(no participant emails provided)'}")
    print(f"Subject: {draft.subject}")
    print(f"Spec:    {draft_path}")
    print("Create:  open this MoM via Claude and ask it to create the Gmail draft,")
    print("         or use mom.html as the email body. Never auto-sent.")
    print("─────────────────────────────────────────────────────────────────")
    if not draft.to:
        print("ℹ  Add emails via --participants \"Name <email>\" or --cc to target recipients.")


def _split(spec: str | None):
    if not spec:
        return []
    return [s.strip() for s in spec.replace(";", ",").split(",") if s.strip()]


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #
def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--title", default="", help="Meeting title")
    p.add_argument("--datetime", default="", help="ISO date/time (default: now)")
    p.add_argument(
        "--participants",
        default="",
        help='Semicolon-separated, e.g. "You (Host); Jane Doe (Acme, VP) <jane@acme.com>"',
    )
    p.add_argument("--agenda", help="Path to an agenda file (one item per line)")
    p.add_argument("--host-name", default="Host", help="Your name (used as 'Prepared by')")
    p.add_argument("--language", default="en", help="Spoken language code (default: en)")
    p.add_argument("--model", default=DEFAULT_MOM_MODEL, help=f"MoM model (default: {DEFAULT_MOM_MODEL})")
    p.add_argument(
        "--output-dir",
        default=str(Path.home() / "meeting-mom"),
        help="Where to write the MoM bundle (default: ~/meeting-mom)",
    )
    p.add_argument("--no-clipboard", action="store_true", help="Don't copy the MoM to the clipboard")
    p.add_argument("--email-draft", action="store_true", help="Prepare a Gmail draft to attendees (never auto-sent)")
    p.add_argument("--cc", default="", help="Extra recipient emails (comma/semicolon separated)")
    p.add_argument("--api-key", help="OPENAI_API_KEY (persisted to OS keyring if available)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Client-meeting minutes from Google Meet (Whisper + GPT-4o)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-devices", help="List input/output audio devices")
    p_list.set_defaults(func=_cmd_list_devices)

    p_check = sub.add_parser("check-audio", help="Verify per-channel audio routing")
    p_check.add_argument("--device", required=True, help="Device name or index")
    p_check.add_argument("--seconds", type=float, default=5.0)
    p_check.set_defaults(func=_cmd_check_audio)

    p_rec = sub.add_parser("record", help="Capture a live meeting and generate a MoM")
    _add_common(p_rec)
    p_rec.add_argument("--device", required=True, help="Aggregate Device name or index")
    p_rec.add_argument("--host-channel", type=int, default=0)
    p_rec.add_argument("--client-channel", type=int, default=1)
    p_rec.set_defaults(func=_cmd_record)

    p_sim = sub.add_parser("simulate", help="Replay a stereo WAV through the pipeline (offline)")
    _add_common(p_sim)
    p_sim.add_argument("--wav", required=True, help="Stereo WAV (ch0=host, ch1=client)")
    p_sim.set_defaults(func=_cmd_simulate)

    p_ft = sub.add_parser("from-transcript", help="Generate a MoM from an existing transcript file")
    _add_common(p_ft)
    p_ft.add_argument("--file", required=True, help="Transcript text file")
    p_ft.set_defaults(func=_cmd_from_transcript)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
