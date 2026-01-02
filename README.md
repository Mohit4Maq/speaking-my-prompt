# Speech-to-Text & Minutes of Meeting (MoM) Pipeline

Convert Google Meet recordings or live voice into accurate transcripts and structured meeting minutes using OpenAI Whisper API. Integrated with VS Code Copilot for instant translation and code generation.

## ✨ What It Does

### 1. **Live Voice Recording & Transcription** (Quickest way to get started)
```bash
voice
```
- 🎤 Records your voice (press Ctrl+C to stop)
- 📝 Transcribes to text using OpenAI Whisper
- 📋 Copies transcript to clipboard automatically
- 💬 Paste into VS Code Copilot for translation, code generation, or analysis

### 2. **File-Based Transcription** (For existing recordings)
```bash
python live_transcribe_only.py --language en
```
- Transcribes MP3, MP4, WAV, M4A, WebM files
- Saves audio + transcript + metadata
- Supports 100+ languages

### 3. **Automatic Google Meet Recording Processing** (For production)
```bash
python -m src.mom_pipeline.watcher --watch ~/Downloads
```
- Monitors a folder for new recordings
- Auto-transcribes when files appear
- Generates structured MoM (Minutes of Meeting)

### 4. **Full MoM Generation Pipeline** (For meetings)
```bash
python mom_cli.py --source meeting.mp4 --title "Quarterly Review" --participants "Alice,Bob"
```
- Transcribes audio/video
- Extracts decisions, action items, risks, open questions
- Generates JSON + Markdown reports
- Ready for Notion, Slack, Jira automation

---

## 🚀 Quick Start (5 minutes)

### Prerequisites
- **macOS** with zsh shell
- **ffmpeg** (installed via Homebrew)
- **OpenAI API Key** (from https://platform.openai.com/api-keys)

### 1. Install Dependencies
```bash
# Install ffmpeg (one-time)
brew install ffmpeg

# Clone/navigate to project
cd /Users/mohitchand/Python/speech_text

# Create Python environment
python -m venv .venv
source .venv/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### 2. Set Up API Key
Create a `.env` file in the project root:
```bash
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

(Get your key from: https://platform.openai.com/api-keys)

### 3. Enable `voice` Command (Optional but Recommended)
```bash
# This was already added to your ~/.zshrc, just verify:
source ~/.zshrc
which voice
# Should show: voice: aliased to voice_to_copilot
```

### 4. Test It
```bash
voice
# Speak something, then Ctrl+C
# ✓ Transcript copied to clipboard!
```

---

## 📖 Usage Guide

### For Non-Coders: Use the `voice` Command

**Scenario: You want to translate your speech to Hindi using Copilot**

1. **Open Terminal** (any folder)
2. **Type:**
   ```bash
   voice
   ```
3. **Speak your English text** (e.g., "Translate this to Hindi: Hello, how are you?")
4. **Press Ctrl+C** when done
5. **Copy notification appears** → transcript is in clipboard
6. **Open VS Code** → Copilot Chat (Cmd+I)
7. **Paste** (Cmd+V) → Ask for Hindi translation
8. **Done!** 🎉

**Files saved automatically:**
- `outputs/<timestamp>_recording/audio_original.wav` — Your voice recording
- `outputs/<timestamp>_recording/transcript.txt` — English text
- `outputs/<timestamp>_recording/transcript_segments.json` — Detailed timestamps
- `outputs/<timestamp>_recording/metadata.json` — Duration, processing time

---

### For Developers: Full Pipeline Options

#### Option A: Live Transcription (Simple)
```bash
python live_transcribe_only.py --language en --copy-to-clipboard
```
- Saves audio + transcript
- Auto-copies to clipboard for Copilot
- No MoM generation

#### Option B: File Processing (Intermediate)
```bash
python mom_cli.py \
  --source ~/Downloads/meeting.mp4 \
  --title "Team Standup" \
  --participants "Alice,Bob,Carol" \
  --output-dir outputs
```
- Processes local or Google Drive files
- Generates structured MoM
- Outputs: transcript + MoM JSON + MoM Markdown + metadata

#### Option C: Folder Watcher (Production)
```bash
python -m src.mom_pipeline.watcher \
  --watch ~/Downloads \
  --output-dir outputs \
  --title-prefix "Meet: "
```
- Monitors folder for new recordings
- Auto-processes when file appears
- Perfect for Google Drive integration

#### Option D: Launch on Startup (Advanced)
Set up a LaunchAgent to auto-start the watcher on login:
- Create `~/Library/LaunchAgents/com.mom.watcher.plist`
- Use `launchctl load` to enable
- (See original README.md for full plist template)

---

## 📁 Project Structure

```
speech_text/
├── live_transcribe_only.py          # Main script: voice → transcript
├── mom_cli.py                        # CLI: file → MoM
├── .voice_alias.sh                   # Bash alias for `voice` command
├── requirements.txt                  # Python dependencies
├── .env                              # API key (create manually, git-ignored)
├── .gitignore                        # Git ignore rules
├── README.md                         # Main documentation (this file)
├── VOICE_COPILOT.md                  # Copilot integration guide
├── src/mom_pipeline/
│   ├── live_capture.py               # Microphone capture + preprocessing
│   ├── live_transcribe.py            # Whisper transcription
│   ├── transcribe.py                 # File-based transcription
│   ├── intake.py                     # File validation + conversion
│   ├── postprocess.py                # Cleanup + normalization
│   ├── mom_generate.py               # MoM JSON + Markdown generation
│   ├── watcher.py                    # Folder monitoring
│   ├── config.py                     # Configuration (formats, limits, models)
│   ├── utils.py                      # Utilities (ffmpeg, timestamps, retry)
│   └── __init__.py
└── outputs/
    └── <timestamp>_recording/        # Auto-created output folder
        ├── audio_original.wav
        ├── transcript.txt
        ├── transcript_segments.json
        └── metadata.json
```

---

## 🎯 Supported Languages

Whisper supports 100+ languages. Examples:
- English (en)
- Spanish (es)
- Hindi (hi)
- French (fr)
- German (de)
- Mandarin (zh)

Use `--language` flag:
```bash
python live_transcribe_only.py --language hi  # Hindi
python live_transcribe_only.py --language es  # Spanish
```

---

## 🔧 Advanced Features

### Generate Minutes of Meeting (MoM)

```bash
python mom_cli.py \
  --source meeting.mp4 \
  --title "Quarterly Planning" \
  --datetime "2026-01-02T10:00:00" \
  --participants "Alice,Bob,Carol" \
  --output-dir outputs
```

**Generates:**
- `transcript_cleaned.txt` — Clean transcript
- `transcript_cleaned.json` — Segments with timestamps
- `mom.json` — Structured data:
  - Meeting title, date, participants
  - Agenda items
  - Discussion points by topic
  - Decisions taken
  - Action items (task, owner, due date, priority)
  - Risks & dependencies
  - Open questions
  - Summary
- `mom.md` — Human-readable Markdown
- `metadata.json` — Processing metrics

### Send to Slack

```bash
curl -X POST https://hooks.slack.com/services/XXX/YYY/ZZZ \
  -H "Content-type: application/json" \
  --data "{\"text\": \"$(cat outputs/.../mom.md)\"}"
```

### Send to Notion

Use the `mom.json` output with Notion API:
```python
import requests
import json

mom = json.load(open("outputs/.../mom.json"))
requests.post("https://api.notion.com/v1/pages", ...)
```

---

## ⚙️ Environment Setup

### macOS (Recommended)
```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install ffmpeg
brew install ffmpeg

# Verify
ffmpeg -version
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `ffmpeg not found` | `brew install ffmpeg` |
| `OPENAI_API_KEY not set` | Create `.env` with `OPENAI_API_KEY=sk-...` |
| `Permission denied: ~/.zshrc` | Run: `sudo chown $USER ~/.zshrc` |
| No speech detected | Ensure mic input is on; speak clearly |
| Whisper timeout | File too large; will auto-split |

---

## 📊 Output Examples

### Sample Transcript (transcript.txt)
```
Hello team. Today we will review Q1 goals, resourcing, and risks.
Decision: prioritize EU expansion.
Action: Alice to prepare market analysis by January 15.
Open question: budget approval timing.
```

### Sample MoM (mom.json)
```json
{
  "meetingTitle": "Quarterly Planning",
  "dateTime": "2026-01-02T10:00:00",
  "platform": "Google Meet",
  "participants": ["Alice", "Bob", "Carol"],
  "agenda": ["Q1 goals", "Resourcing", "Risks"],
  "decisions": ["Prioritize EU expansion"],
  "actionItems": [
    {
      "task": "Market analysis EU",
      "owner": "Alice",
      "dueDate": "2026-01-15",
      "priority": "High"
    }
  ],
  "risks": ["Supply chain delays"],
  "openQuestions": ["Budget approval timing"],
  "summary": ["Q1 growth focused", "EU expansion prioritized"]
}
```

### Sample MoM (mom.md)
```markdown
# Minutes of Meeting: Quarterly Planning

- Date & Time: 2026-01-02T10:00:00
- Platform: Google Meet
- Participants: Alice, Bob, Carol

## Agenda
- Q1 goals
- Resourcing
- Risks

## Decisions Taken
- Prioritize EU expansion

## Action Items
- Task: Market analysis EU | Owner: Alice | Due: 2026-01-15 | Priority: High

## Open Questions
- Budget approval timing
```

---

## 🔐 Security & Privacy

- **Local Processing:** Audio is processed locally (no permanent storage after transcription)
- **API Key:** Stored in `.env` (git-ignored, never committed)
- **No Hallucination:** Whisper transcribes only what's spoken
- **Deterministic:** MoM generation uses temperature=0 for consistent outputs

---

## 📝 Git & Version Control

```bash
# Initialize git (if needed)
git init

# Add remote (replace with your repo URL)
git remote add origin https://github.com/yourusername/speech_text.git

# Commit & push
git add .
git commit -m "Initial: speech-to-text and MoM pipeline"
git push origin main
```

**.gitignore** is included to exclude:
- Python cache & virtual env
- `.env` (API keys)
- `outputs/` (user recordings)
- IDE files (`.vscode`, `.idea`)

---

## 💡 Example Workflows

### Workflow 1: Daily Standup Transcription
```bash
# Every morning
voice
# Speak: "Today I'll work on API endpoints and fix the login bug"
# Ctrl+C → clipboard copy
# Paste in Copilot to expand to detailed notes
```

### Workflow 2: Meeting Recording to Minutes
```bash
# After Google Meet
python mom_cli.py \
  --source ~/Downloads/meeting_recording.mp4 \
  --title "Sprint Planning" \
  --participants "Team" \
  --output-dir outputs

# Open outputs/.../mom.md and share
```

### Workflow 3: Live Translation (English → Hindi)
```bash
# Speak English, translate to Hindi
voice
# Speak: "How to optimize database queries for better performance"
# Ctrl+C
# Paste in Copilot → ask for Hindi translation
```

---

## 🤝 Contributing

Feel free to extend this project:
- Add speaker diarization (who said what)
- Support for custom MoM templates
- Notion/Slack auto-posting
- Real-time live transcription UI

---

## 📜 License

MIT License

---

## ❓ FAQ

**Q: Does it require internet?**  
A: Yes, Whisper API requires OpenAI connectivity. Local Whisper (offline) is available but not used here.

**Q: Is my audio private?**  
A: Audio is sent to OpenAI Whisper API. It's not stored; use a paid API key for guaranteed privacy.

**Q: Can I use it without VS Code?**  
A: Yes! The transcript is saved to files and clipboard. You can use any text editor.

**Q: How much does it cost?**  
A: OpenAI Whisper: $0.006 per minute of audio. Very cheap!

**Q: Can I use a different speech-to-text?**  
A: This pipeline uses Whisper specifically. Alternatives: Google Cloud Speech-to-Text, AWS Transcribe.

---

## 🎉 You're All Set!

Start with:
```bash
voice
```

Enjoy hands-free speech-to-text and Copilot integration! 🚀

---

**Questions?** Check `VOICE_COPILOT.md` for Copilot-specific tips.
