"""Real-time transcription from live audio chunks."""
import io
from typing import Tuple, Dict, List
from openai import OpenAI
from scipy.io import wavfile
import numpy as np


def transcribe_audio(audio_bytes: bytes, language: str = "en") -> Tuple[str, List[Dict]]:
    """
    Transcribe full audio file via Whisper with detailed segments.
    Uses response_format=verbose_json to get segment-level timing and text.
    Returns (full_text, segments).
    """
    client = OpenAI()
    try:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", io.BytesIO(audio_bytes), "audio/wav"),
            language=language,
            response_format="verbose_json",
        )
        
        full_text = result.text.strip()
        segments = []
        
        if hasattr(result, 'segments'):
            for seg in result.segments:
                # Handle both dict and object responses
                if isinstance(seg, dict):
                    segments.append({
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0),
                        "text": seg.get("text", "").strip(),
                    })
                else:
                    # TranscriptionSegment object
                    segments.append({
                        "start": getattr(seg, "start", 0),
                        "end": getattr(seg, "end", 0),
                        "text": getattr(seg, "text", "").strip(),
                    })
        
        return (full_text, segments)
    except Exception as e:
        print(f"Transcription error: {e}")
        import traceback
        traceback.print_exc()
        return ("", [])


def transcribe_chunk(audio_bytes: bytes, language: str = "en") -> str:
    """Transcribe a single audio chunk via Whisper API."""
    client = OpenAI()
    try:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=("chunk.wav", io.BytesIO(audio_bytes), "audio/wav"),
            language=language,
        )
        return result.text.strip()
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""


def stream_transcription(
    audio_bytes: bytes,
    sample_rate: int = 16000,
    chunk_duration: float = 5.0,
    language: str = "en",
) -> Tuple[str, list]:
    """
    Transcribe audio using full-file approach (reduces hallucination vs overlapping chunks).
    Returns (full_text, segments).
    """
    full_text, segments = transcribe_audio(audio_bytes, language)
    
    # Print each segment with timing
    for seg in segments:
        if seg["text"]:
            print(f"[{seg['start']:.1f}s-{seg['end']:.1f}s] {seg['text']}")
    
    return (full_text, segments)
