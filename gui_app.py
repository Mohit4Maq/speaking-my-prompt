#!/usr/bin/env python3
"""Minimal macOS GUI for voice → transcript with OpenAI Whisper.
- Asks for API key (entry) and records via microphone.
- Transcribes using existing pipeline and shows text.
- Copies transcript to clipboard.

Note: For a signed .app/.dmg, you must build with py2app and sign/notarize separately.
"""
import os
import threading
import tkinter as tk
from tkinter import messagebox

import pyperclip

from mom_pipeline.live_capture import stream_audio
from mom_pipeline.live_transcribe import transcribe_audio


def run_transcription(api_key: str, language: str, status_var, text_var, btn):
    if not api_key:
        messagebox.showerror("Missing API Key", "Please enter your OPENAI_API_KEY.")
        return

    os.environ["OPENAI_API_KEY"] = api_key

    def worker():
        try:
            status_var.set("Recording... Press Stop when done.")
            btn.config(state=tk.DISABLED)
            audio_bytes = stream_audio(duration=None)
            status_var.set("Transcribing...")
            full_text, _ = transcribe_audio(audio_bytes, language=language)
            if not full_text.strip():
                status_var.set("No speech detected.")
            else:
                text_var.set(full_text)
                try:
                    pyperclip.copy(full_text)
                    status_var.set("Done. Transcript copied to clipboard.")
                except Exception:
                    status_var.set("Done. Transcript ready (clipboard copy failed).")
        except Exception as e:
            status_var.set(f"Error: {e}")
        finally:
            btn.config(state=tk.NORMAL)

    threading.Thread(target=worker, daemon=True).start()


def main():
    root = tk.Tk()
    root.title("Voice to Transcript (Whisper)")
    root.geometry("520x380")

    tk.Label(root, text="OPENAI_API_KEY:").pack(anchor="w", padx=10, pady=(10, 0))
    api_entry = tk.Entry(root, width=60, show="*")
    api_entry.pack(fill="x", padx=10)

    tk.Label(root, text="Language (e.g., en, hi, es):").pack(anchor="w", padx=10, pady=(10, 0))
    lang_entry = tk.Entry(root, width=10)
    lang_entry.insert(0, "en")
    lang_entry.pack(anchor="w", padx=10)

    status_var = tk.StringVar()
    status_var.set("Idle")

    text_var = tk.StringVar()

    btn = tk.Button(
        root,
        text="Record & Transcribe",
        command=lambda: run_transcription(
            api_entry.get().strip(), lang_entry.get().strip() or "en", status_var, text_var, btn
        ),
        bg="#4CAF50",
        fg="white",
        padx=10,
        pady=6,
    )
    btn.pack(pady=10)

    status_label = tk.Label(root, textvariable=status_var, fg="blue")
    status_label.pack(anchor="w", padx=10)

    tk.Label(root, text="Transcript:").pack(anchor="w", padx=10, pady=(10, 0))
    text_box = tk.Text(root, height=10, wrap="word")
    text_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def on_text_var_change(*_):
        text_box.delete("1.0", tk.END)
        text_box.insert(tk.END, text_var.get())

    text_var.trace_add("write", on_text_var_change)

    root.mainloop()


if __name__ == "__main__":
    main()
