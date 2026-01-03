#!/usr/bin/env python
"""CLI entrypoint for lazy_prompt: live mic → transcript (and clipboard).

Usage:
    lazy-prompt --language en --output-dir outputs --copy-to-clipboard

Environment:
    OPENAI_API_KEY must be set (load from .env if present).
"""
import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import pyperclip
from openai import OpenAI

try:
    import keyring
except Exception:
    keyring = None

from lazy_prompt.interactive import interactive_refinement_flow


def _get_api_key(arg_key: str | None) -> str | None:
    if arg_key:
        return arg_key
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key
    if keyring:
        try:
            return keyring.get_password("lazy-prompt", "OPENAI_API_KEY")
        except Exception:
            return None
    return None


def _persist_api_key(api_key: str | None) -> None:
    if not api_key or not keyring:
        return
    try:
        keyring.set_password("lazy-prompt", "OPENAI_API_KEY", api_key)
    except Exception:
        pass


def _enhance_prompt(raw_text: str) -> str:
    """Use GPT-4 to enhance the user's spoken prompt with expert prompt engineering."""
    client = OpenAI()
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert prompt engineer. The user will provide a casual, spoken prompt. "
                        "Your job is to:\n"
                        "1. Understand the user's intent deeply\n"
                        "2. Expand it into a highly structured, detailed, and expert-level prompt\n"
                        "3. Use bullet points, clear sections, and specific instructions\n"
                        "4. Add relevant context, constraints, and desired output format\n"
                        "5. Make it actionable and comprehensive\n\n"
                        "Return ONLY the enhanced prompt, no meta-commentary."
                    ),
                },
                {"role": "user", "content": raw_text},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"\nWarning: Prompt enhancement failed: {e}")
        return raw_text


def run_once(
    output_dir: Path,
    language: str,
    copy_to_clipboard: bool,
    save_outputs: bool,
    translate_to_english: bool,
    api_key: str | None,
    enhance_prompt: bool,
    interactive_mode: bool,
) -> int:
    load_dotenv()

    key = _get_api_key(api_key)
    if not key:
        print("Missing OPENAI_API_KEY. Pass --api-key once or set env/Keychain.")
        return 1
    os.environ["OPENAI_API_KEY"] = key
    _persist_api_key(api_key)

    print("\n=== lazy_prompt: Voice → Transcript ===")
    print(f"Language: {language}")
    print("\nStarting voice capture. Press Ctrl+C to stop.\n")

    start_time = time.time()
    try:
        audio_bytes = stream_audio(duration=None)
    except KeyboardInterrupt:
        print("\nCapture interrupted.")
        return 1

    print("\nTranscribing with Whisper...")
    try:
        if translate_to_english:
            full_text, segments = translate_audio(audio_bytes, source_language=language)
        else:
            full_text, segments = transcribe_audio(audio_bytes, language=language)
    except Exception as exc:  # noqa: BLE001
        print(f"Transcription error: {exc}")
        return 1

    if not full_text.strip():
        print("No speech detected. Exiting.")
        return 1
    # Interactive refinement mode
    if interactive_mode:
        print("\nStarting interactive refinement...")
        final_text = interactive_refinement_flow(full_text, language=language, api_key=key)
    elif enhance_prompt:
        # Standard enhancement without interaction
        print("\nEnhancing prompt with GPT-4...")
        enhanced_text = _enhance_prompt(full_text)
        print("\n=== Enhanced Prompt ===")
        print(enhanced_text)
        print("======================\n")
        final_text = enhanced_text
    else:
        final_text = full_text

    if save_outputs:
        ts = now_ts()
        out_dir = output_dir / f"{ts}_recording"
        ensure_dir(out_dir)

        # Save raw audio file
        (out_dir / "audio_original.wav").write_bytes(audio_bytes)

        # Save transcript
        (out_dir / "transcript.txt").write_text(full_text)
        if enhance_prompt or interactive_mode:
            (out_dir / "enhanced_prompt.txt").write_text(final_text)

        # Save segments as JSON
        safe_json_dump({"segments": segments}, out_dir / "transcript_segments.json")

        # Save metadata
        processing_time = time.time() - start_time
        safe_json_dump(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "language": language,
                "audio_bytes": len(audio_bytes),
                "audio_file": "audio_original.wav",
                "transcript_file": "transcript.txt",
                "processing_time_seconds": processing_time,
                "processing_time": f"{processing_time:.2f}s",
            },
            out_dir / "metadata.json",
        )

    if copy_to_clipboard:
        try:
            pyperclip.copy(final_text)
            mode_desc = "Refined prompt" if interactive_mode else ("Enhanced prompt" if enhance_prompt else "Transcript")
            print(f"\n✓ {mode_desc} copied to clipboard.")
        except Exception as exc:  # noqa: BLE001
            print(f"\nWarning: Could not copy to clipboard: {exc}")
    else:
        print("\n(Clipboard copy skipped; use default or remove --no-clipboard to enable.)")

    if save_outputs:
        print(f"\n✓ Saved to: {out_dir}")
        print(f"  - audio_original.wav ({len(audio_bytes)} bytes)")
        print("  - transcript.txt")
        if enhance_prompt or interactive_mode:
            print("  - enhanced_prompt.txt")
        print("  - transcript_segments.json")
        print("  - metadata.json")
    else:
        print("\n✓ Not saved (default behavior; use --save to write files).")
    if not (enhance_prompt or interactive_mode):
        print(f"\nTranscript:\n{full_text}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live voice → Audio + Transcript (no files saved by default)")
    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / "lazy-prompt"),
        help="Output directory (default: ~/lazy-prompt)",
    )
    parser.add_argument("--language", default="en", help="Language code (en, es, fr, etc.)")
    parser.add_argument(
        "--no-clipboard",
        action="store_true",
        help="Disable copying transcript to clipboard",
    )
    parser.add_argument(
        "--translate-to-english",
        action="store_true",
        help="Use Whisper translate endpoint to return English even if you speak another language",
    )
    parser.add_argument(
        "--api-key",
        help="Supply and persist your OPENAI_API_KEY once; stored in OS keyring if available",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save audio and transcript files to disk (default: no files saved)",
    )
    parser.add_argument(
        "--enhance-prompt",
        action="store_true",
        help="Use GPT-4 to enhance the transcript into an expert-level, structured prompt",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enable interactive mode: AI asks clarifying questions to refine your prompt through dialogue",
    )

    args = parser.parse_args(argv)
    return run_once(
        Path(args.output_dir).expanduser(),
        args.language,
        copy_to_clipboard=not args.no_clipboard,
        save_outputs=args.save,
        translate_to_english=args.translate_to_english,
        api_key=args.api_key,
        enhance_prompt=args.enhance_prompt,
        interactive_mode=args.interactive,
    )


if __name__ == "__main__":
    sys.exit(main())
