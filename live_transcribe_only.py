#!/usr/bin/env python
"""Simple live voice capture, transcription, and save (no MoM generation)."""
import argparse
import time
from datetime import datetime

from dotenv import load_dotenv
import pyperclip

from src.mom_pipeline.live_capture import stream_audio
from src.mom_pipeline.live_transcribe import transcribe_audio
from src.mom_pipeline.utils import ensure_dir, now_ts, safe_json_dump


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Live voice → Audio + Transcript")
    parser.add_argument("--output-dir", default="outputs", help="Output directory")
    parser.add_argument("--language", default="en", help="Language code (en, es, fr, etc.)")
    parser.add_argument("--copy-to-clipboard", action="store_true", help="Copy transcript to clipboard for Copilot")
    args = parser.parse_args()

    print("\n=== Live Voice Recording & Transcription ===")
    print(f"Language: {args.language}")
    print("\nStarting voice capture. Press Ctrl+C to stop.\n")

    start_time = time.time()

    try:
        # Capture audio from mic with preprocessing
        audio_bytes = stream_audio(duration=None)
    except KeyboardInterrupt:
        print("\nCapture interrupted.")
        return

    print("\nTranscribing with Whisper...")
    try:
        full_text, segments = transcribe_audio(audio_bytes, language=args.language)
    except Exception as e:
        print(f"Transcription error: {e}")
        return

    if not full_text.strip():
        print("No speech detected. Exiting.")
        return

    # Save outputs
    ts = now_ts()
    out_dir = f"{args.output_dir}/{ts}_recording"
    ensure_dir(out_dir)

    # Save raw audio file
    with open(f"{out_dir}/audio_original.wav", "wb") as f:
        f.write(audio_bytes)

    # Save transcript
    with open(f"{out_dir}/transcript.txt", "w") as f:
        f.write(full_text)

    # Save segments as JSON
    safe_json_dump({"segments": segments}, f"{out_dir}/transcript_segments.json")

    # Save metadata
    processing_time = time.time() - start_time
    safe_json_dump(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "language": args.language,
            "audio_bytes": len(audio_bytes),
            "audio_file": "audio_original.wav",
            "transcript_file": "transcript.txt",
            "processing_time_seconds": processing_time,
            "processing_time": f"{processing_time:.2f}s",
        },
        f"{out_dir}/metadata.json",
    )

    # Optionally copy to clipboard for Copilot
    if args.copy_to_clipboard:
        try:
            pyperclip.copy(full_text)
            print("\n✓ Transcript copied to clipboard!")
            print("  Paste it in VS Code Copilot chat or code comments.")
        except Exception as e:
            print(f"\nWarning: Could not copy to clipboard: {e}")

    print(f"\n✓ Saved to: {out_dir}")
    print(f"  - audio_original.wav ({len(audio_bytes)} bytes)")
    print(f"  - transcript.txt")
    print(f"  - transcript_segments.json")
    print(f"  - metadata.json")
    print(f"\nTranscript:\n{full_text}")


if __name__ == "__main__":
    main()
