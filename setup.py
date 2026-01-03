"""py2app setup for packing gui_app.py into a macOS .app"""
from setuptools import setup

APP = ["gui_app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": True,
    # Explicit includes help py2app collect Tkinter and deps when not in alias mode.
    "includes": ["tkinter"],
    "packages": ["src", "pyperclip", "sounddevice", "numpy", "scipy", "openai", "ffmpeg"],
    "plist": {
        "CFBundleName": "VoiceToTranscript",
        "CFBundleDisplayName": "VoiceToTranscript",
        "CFBundleIdentifier": "com.example.voicetotranscript",
        "NSMicrophoneUsageDescription": "Microphone is used to capture audio for transcription.",
    },
}

setup(app=APP, data_files=DATA_FILES, options={"py2app": OPTIONS}, setup_requires=["py2app"])
