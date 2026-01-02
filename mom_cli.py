import argparse
import os
import time

from dotenv import load_dotenv
from src.mom_pipeline.intake import resolve_source, validate_and_convert, split_if_needed
from src.mom_pipeline.transcribe import transcribe_files
from src.mom_pipeline.postprocess import normalize_segments, segments_to_text
from src.mom_pipeline.mom_generate import generate_mom, render_markdown
from src.mom_pipeline.utils import (
    ensure_dir,
    ffprobe_duration,
    now_ts,
    safe_json_dump,
    size_to_str,
)


def main():
    parser = argparse.ArgumentParser(description="Google Meet → MoM Pipeline")
    parser.add_argument("--source", required=True, help="Local path or Google Drive URL")
    parser.add_argument("--title", default="", help="Meeting title")
    parser.add_argument("--datetime", default="", help="Meeting date/time (ISO 8601 if available)")
    parser.add_argument("--participants", default="", help="Comma-separated participant names")
    parser.add_argument("--output-dir", default="outputs", help="Directory to write outputs")
    args = parser.parse_args()

    # Load environment variables from .env if present (current dir and script dir)
    load_dotenv()
    # Also load .env next to this script so watcher/launchd runs find it
    script_dir = os.path.dirname(os.path.abspath(__file__))
    from dotenv import find_dotenv
    local_env = os.path.join(script_dir, ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env, override=False)
    else:
        # try find_dotenv relative to script_dir
        found = find_dotenv(filename=".env", usecwd=False)
        if found:
            load_dotenv(found, override=False)

    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        raise SystemExit("OPENAI_API_KEY environment variable not set.")

    start_time = time.time()

    # Prepare working/output dirs
    ts = now_ts()
    base = os.path.basename(args.source)
    out_dir = os.path.join(args.output_dir, f"{ts}_{os.path.splitext(base)[0]}")
    work_dir = os.path.join(out_dir, "work")
    ensure_dir(out_dir)
    ensure_dir(work_dir)

    # Intake
    local_input = resolve_source(args.source, work_dir)
    audio_path = validate_and_convert(local_input, work_dir)
    chunks = split_if_needed(audio_path, work_dir)

    # Transcription
    raw_text, segments_raw = transcribe_files(chunks)

    # Post-processing
    segments = normalize_segments(segments_raw)
    cleaned_text = segments_to_text(segments)

    # Metadata
    duration = ffprobe_duration(audio_path) or 0.0
    size_bytes = sum(os.path.getsize(p) for p in chunks)

    meta = {
        "duration_seconds": duration,
        "duration": f"{duration:.2f}s",
        "file_size_bytes": size_bytes,
        "file_size": size_to_str(size_bytes),
        "processing_time_seconds": time.time() - start_time,
        "processing_time": f"{time.time() - start_time:.2f}s",
    }

    # MoM generation
    participants = [p.strip() for p in args.participants.split(",") if p.strip()] if args.participants else []
    mom = generate_mom(
        transcript_text=cleaned_text,
        metadata={"title": args.title, "datetime": args.datetime, "participants": participants},
    )
    mom_md = render_markdown(mom)

    # Outputs
    with open(os.path.join(out_dir, "transcript_cleaned.txt"), "w", encoding="utf-8") as f:
        f.write(cleaned_text)

    safe_json_dump({"segments": segments}, os.path.join(out_dir, "transcript_cleaned.json"))
    safe_json_dump(mom, os.path.join(out_dir, "mom.json"))
    safe_json_dump(meta, os.path.join(out_dir, "metadata.json"))

    with open(os.path.join(out_dir, "mom.md"), "w", encoding="utf-8") as f:
        f.write(mom_md)

    print("\nCompleted. Outputs:")
    print(f"- {os.path.join(out_dir, 'transcript_cleaned.txt')}")
    print(f"- {os.path.join(out_dir, 'transcript_cleaned.json')}")
    print(f"- {os.path.join(out_dir, 'mom.json')}")
    print(f"- {os.path.join(out_dir, 'mom.md')}")
    print(f"- {os.path.join(out_dir, 'metadata.json')}")


if __name__ == "__main__":
    main()
