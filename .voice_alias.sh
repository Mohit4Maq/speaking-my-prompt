#!/bin/bash
# Quick launcher: record voice, transcribe, copy to clipboard, show file location
# Source this or add to .zshrc for easy access

function voice_to_copilot() {
    cd /Users/mohitchand/Python/speech_text
    source .venv/bin/activate
    python live_transcribe_only.py --language en --copy-to-clipboard
    echo ""
    echo "✓ Transcript is in your clipboard!"
    echo "  Open VS Code Copilot (Cmd+I or Cmd+Shift+I) and paste."
}

alias voice="voice_to_copilot"
