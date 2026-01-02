# Voice → Copilot Integration

Add this to your `~/.zshrc` for a quick `voice` command:

```bash
# At the end of ~/.zshrc
source /Users/mohitchand/Python/speech_text/.voice_alias.sh
```

Then reload:
```bash
source ~/.zshrc
```

## Usage

From any terminal:
```bash
voice
```

This will:
1. Record your voice (press Ctrl+C to stop)
2. Transcribe with Whisper
3. **Copy transcript to clipboard**
4. Show file location

Then in VS Code:
- Open Copilot Chat: **Cmd+I** or **Cmd+Shift+I**
- Paste (Cmd+V)
- Ask Copilot to implement, explain, or generate code

## Example Workflow

```bash
voice
# Speak: "write a function that validates email addresses"
# (press Ctrl+C)
# ✓ Transcript is in your clipboard!
```

In VS Code Copilot:
- Paste the transcript
- Copilot generates the code based on your voice prompt

## Files Created

- `live_transcribe_only.py --copy-to-clipboard`: Copies transcript to clipboard
- `.voice_alias.sh`: Bash alias for easy access
