#!/usr/bin/env python
"""Interactive CLI for live voice input and real-time MoM generation."""
import argparse
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

from mom_pipeline.live_capture import stream_audio
from mom_pipeline.live_transcribe import stream_transcription
from mom_pipeline.postprocess import normalize_segments, segments_to_text
from mom_pipeline.mom_generate import generate_mom, render_markdown
from mom_pipeline.utils import ensure_dir, now_ts, safe_json_dump


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Live voice → MoM")
    parser.add_argument("--title", default="Live Meeting", help="Meeting title")
    parser.add_argument("--participants", default="", help="Comma-separated names")
    parser.add_argument("--output-dir", default="outputs", help="Output directory")
    parser.add_argument("--language", default="en", help="Language code (en, es, fr, etc.)")
    args = parser.parse_args()

    print("\n=== Live Voice to MoM ===")
    print(f"Meeting: {args.title}")
    print(f"Language: {args.language}")
    print("\nStarting voice capture. Press Ctrl+C to stop and generate MoM.\n")

    start_time = time.time()

    try:
        # Capture audio from mic with preprocessing
        audio_bytes = stream_audio(duration=None)
    except KeyboardInterrupt:
        print("\nCapture interrupted.")
        return

    print("\nTranscribing with Whisper...")
    try:
        full_text, segments = stream_transcription(
            audio_bytes, language=args.language
        )
    except Exception as e:
        print(f"Transcription error: {e}")
        return

    if not full_text.strip():
        print("No speech detected. Exiting.")
        return

    print("\nPost-processing...")
    # Convert segments from Whisper's response_format=verbose_json
    processed_segments = normalize_segments(segments)
    cleaned_text = segments_to_text(processed_segments)

    print("\nGenerating MoM...")
    participants = [p.strip() for p in args.participants.split(",") if p.strip()] if args.participants else []
    mom = generate_mom(
        transcript_text=cleaned_text,
        metadata={
            "title": args.title,
            "datetime": datetime.utcnow().isoformat(),
            "participants": participants,
        },
    )
    mom_md = render_markdown(mom)

    # Save outputs
    ts = now_ts()
    out_dir = f"{args.output_dir}/{ts}_live"
    ensure_dir(out_dir)

    # Save raw audio file
    with open(f"{out_dir}/audio_original.wav", "wb") as f:
        f.write(audio_bytes)

    with open(f"{out_dir}/transcript_cleaned.txt", "w") as f:
        f.write(cleaned_text)

    safe_json_dump({"segments": processed_segments}, f"{out_dir}/transcript_cleaned.json")
    safe_json_dump(mom, f"{out_dir}/mom.json")

    with open(f"{out_dir}/mom.md", "w") as f:
        f.write(mom_md)

    processing_time = time.time() - start_time
    safe_json_dump(
        {
            "audio_bytes": len(audio_bytes),
            "audio_file": "audio_original.wav",
            "processing_time_seconds": processing_time,
            "processing_time": f"{processing_time:.2f}s",
        },
        f"{out_dir}/metadata.json",
    )

    print(f"\n✓ Outputs saved to: {out_dir}")
    print(f"  - audio_original.wav ({len(audio_bytes)} bytes)")
    print(f"  - transcript_cleaned.txt")
    print(f"  - transcript_cleaned.json")
    print(f"  - mom.json")
    print(f"  - mom.md")
    print(f"  - metadata.json")
    print(f"\nTranscript (cleaned):\n{cleaned_text}\n")
    print(f"MoM:\n{mom_md}")


if __name__ == "__main__":
    main()
