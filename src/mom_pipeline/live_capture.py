"""Live microphone capture and streaming to Whisper."""
import io
import queue
from typing import Callable, Optional

import sounddevice as sd
from scipy.io import wavfile
from scipy import signal
import numpy as np


def stream_audio(
    duration: Optional[float] = None,
    sample_rate: int = 16000,
    blocksize: int = 4096,
    on_chunk: Optional[Callable[[bytes], None]] = None,
) -> bytes:
    """
    Capture audio from microphone and optionally call on_chunk for each block.
    Returns full audio as WAV bytes.
    """
    audio_queue = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(f"Audio status: {status}")
        audio_queue.put(indata.copy())

    # Start recording
    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        blocksize=blocksize,
        callback=audio_callback,
        dtype=np.float32,
    )
    stream.start()

    print("Recording... (Press Ctrl+C to stop)")
    audio_data = []
    try:
        while True:
            chunk = audio_queue.get(timeout=0.5 if duration is None else (duration / 10))
            audio_data.append(chunk)
            if on_chunk:
                # Convert chunk to bytes for Whisper
                wav_bytes = _array_to_wav(chunk, sample_rate)
                on_chunk(wav_bytes)
            if duration and len(audio_data) * (blocksize / sample_rate) >= duration:
                break
    except KeyboardInterrupt:
        print("\nRecording stopped.")
    finally:
        stream.stop()
        stream.close()

    # Concatenate and preprocess all audio data
    full_audio = np.concatenate(audio_data, axis=0)
    full_audio = _preprocess_audio(full_audio, sample_rate)
    return _array_to_wav(full_audio, sample_rate)


def _preprocess_audio(audio_array: np.ndarray, sample_rate: int) -> np.ndarray:
    """
    Preprocess audio: normalize, remove DC offset, apply gentle high-pass filter.
    Reduces hallucination by cleaning up background noise and improving clarity.
    """
    # Remove DC offset
    audio_array = audio_array - np.mean(audio_array)
    
    # Normalize to prevent clipping (keep some headroom)
    max_val = np.max(np.abs(audio_array))
    if max_val > 0:
        audio_array = audio_array / (max_val * 1.1)
    
    # Apply gentle high-pass filter to reduce low-frequency rumble
    # 80 Hz cutoff
    sos = signal.butter(5, 80, 'hp', fs=sample_rate, output='sos')
    audio_array = signal.sosfilt(sos, audio_array)
    
    # Re-normalize after filtering
    max_val = np.max(np.abs(audio_array))
    if max_val > 0:
        audio_array = audio_array / (max_val * 1.1)
    
    return audio_array


def _array_to_wav(audio_array: np.ndarray, sample_rate: int) -> bytes:
    """Convert numpy audio array to WAV bytes."""
    # Ensure float32 and in range [-1, 1]
    audio_array = np.asarray(audio_array, dtype=np.float32)
    audio_array = np.clip(audio_array, -1.0, 1.0)
    
    # Convert to int16 with proper scaling
    audio_int16 = np.int16(audio_array * 32767)
    
    # Write to bytes buffer
    buffer = io.BytesIO()
    wavfile.write(buffer, sample_rate, audio_int16)
    buffer.seek(0)
    return buffer.read()
