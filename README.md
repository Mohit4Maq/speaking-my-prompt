# Lazy Prompt - Voice-to-Text CLI with AI Enhancement

**Transform your voice into polished, structured prompts with OpenAI Whisper and GPT-4.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## 📋 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)
- [Future Enhancements](#-future-enhancements)

## ✨ Features

**Simple command for instant voice-to-text:**
```bash
lazy-prompt --language en
```

**What it does:**
- 🎤 **Records your voice** - High-quality audio capture with preprocessing
- 🌍 **100+ languages** - Supports English, Hindi, Spanish, French, and more
- 📝 **AI transcription** - OpenAI Whisper API for accurate speech-to-text
- 📋 **Auto-clipboard** - Instantly copies to clipboard for easy pasting
- 🚀 **GPT-4 enhancement** - Optional: Transform casual speech into expert-level structured prompts
- 🔐 **Secure API storage** - Persist your OpenAI API key in OS keyring (macOS Keychain, Windows Credential Manager)
- 💾 **Minimal footprint** - No files saved by default (clipboard-only mode)

## 🚀 Quick Start

### Prerequisites

**System Requirements:**
- Python 3.10 or higher
- ffmpeg (audio processing)
- OpenAI API Key ([get one here](https://platform.openai.com/api-keys))

**Supported Platforms:**
- macOS (tested)
- Linux (should work)
- Windows (requires ffmpeg installation)

**Install ffmpeg:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (via Chocolatey)
choco install ffmpeg

# Verify installation
ffmpeg -version
```

## 📦 Installation

### Option 1: Install from GitHub (Recommended)

```bash
# Install directly from GitHub
pip install git+https://github.com/Mohit4Maq/speaking-my-prompt.git

# Or using pipx (isolated environment)
pipx install git+https://github.com/Mohit4Maq/speaking-my-prompt.git
```

### Option 2: Local Development Setup

```bash
# Clone repository
git clone https://github.com/Mohit4Maq/speaking-my-prompt.git
cd speaking-my-prompt

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .
```

### Verify Installation

```bash
lazy-prompt --help
```

## 🎯 Usage

### Basic Usage

```bash
# Simple voice-to-text (English)
lazy-prompt --language en

# First-time setup: persist your API key
lazy-prompt --api-key sk-proj-your-key-here --language en
```

**What happens:**
1. Terminal prompts you to start speaking
2. Press `Ctrl+C` when done
3. Whisper transcribes your audio
4. Text is copied to clipboard automatically
5. No files are saved (clipboard-only by default)

### Advanced Features

#### 🚀 GPT-4 Prompt Enhancement

Transform casual speech into expert-level prompts:

```bash
lazy-prompt --enhance-prompt --language en
```

**Example transformation:**

*You speak:* "Create a Python function that reads a CSV file and calculates the average of a column"

*GPT-4 enhances to:*
```
Create a robust Python function with the following specifications:

1. **Function Signature:**
   - Name: `calculate_column_average`
   - Parameters: `file_path` (str), `column_name` (str)
   - Return type: float

2. **Requirements:**
   - Read CSV file using pandas library
   - Handle missing values (skip or fill with 0)
   - Validate column exists before processing
   - Raise appropriate exceptions for errors

3. **Error Handling:**
   - FileNotFoundError for invalid paths
   - KeyError for non-existent columns
   - ValueError for non-numeric data

4. **Output Format:**
   - Return average as float rounded to 2 decimal places
   - Print summary statistics (count, sum, average)
```

#### 🌍 Multi-Language Support

```bash
# Hindi transcription
lazy-prompt --language hi

# Spanish transcription
lazy-prompt --language es

# Auto-translate to English (any language)
lazy-prompt --translate-to-english --language hi
```

**Supported languages:** en, es, fr, de, it, pt, nl, ru, zh, ja, ko, hi, ar, and [90+ more](https://platform.openai.com/docs/guides/speech-to-text/supported-languages)

#### 💾 Save Audio & Transcripts

```bash
# Save to ~/lazy-prompt folder
lazy-prompt --save --language en
```

**Saved files:**
- `audio_original.wav` - Original recording
- `transcript.txt` - Raw transcription
- `enhanced_prompt.txt` - GPT-4 enhanced version (if --enhance-prompt used)
- `transcript_segments.json` - Timestamped segments
- `metadata.json` - Processing metrics

#### ⚙️ All Options

```bash
lazy-prompt \
  --language en \
  --enhance-prompt \
  --save \
  --output-dir ~/my-prompts \
  --api-key sk-your-key

# Disable clipboard (useful for CI/CD)
lazy-prompt --no-clipboard --save
```

### Command Reference

| Flag | Description | Default |
|------|-------------|:-------:|
| `--language` | Language code (en, hi, es, etc.) | `en` |
| `--enhance-prompt` | Use GPT-4 to enhance transcript | `off` |
| `--translate-to-english` | Translate any language to English | `off` |
| `--save` | Save audio/transcript to disk | `off` |
| `--no-clipboard` | Disable clipboard copy | `off` |
| `--output-dir` | Where to save files | `~/lazy-prompt` |
| `--api-key` | Set and persist OpenAI API key | - |

## 📁 Project Structure

```
speaking-my-prompt/
├── README.md                         # Main documentation
├── CONTRIBUTING.md                   # Contribution guidelines
├── CHANGELOG.md                      # Version history
├── LICENSE                           # MIT License
├── pyproject.toml                    # Package metadata & dependencies
├── requirements.txt                  # Development dependencies
├── .gitignore                        # Git ignore rules
├── .env.example                      # Example environment file
│
├── src/
│   ├── lazy_prompt/                  # Main package
│   │   ├── __init__.py
│   │   └── cli.py                    # CLI entrypoint (lazy-prompt command)
│   │
│   └── mom_pipeline/                 # Core modules
│       ├── __init__.py
│       ├── live_capture.py           # Audio capture with preprocessing
│       ├── live_transcribe.py        # Whisper API integration
│       ├── transcribe.py             # File-based transcription
│       ├── intake.py                 # File validation & conversion
│       ├── postprocess.py            # Text cleanup & normalization
│       ├── mom_generate.py           # Meeting minutes generation
│       ├── watcher.py                # Folder monitoring
│       ├── config.py                 # Configuration
│       └── utils.py                  # Utilities
│
├── scripts/
│   └── build_app.sh                  # macOS .app/.dmg builder
│
├── gui_app.py                        # Optional GUI application
├── setup.py                          # py2app configuration
├── live_transcribe_only.py           # Standalone script
├── live_voice_mom.py                 # Meeting minutes script
└── mom_cli.py                        # File processing CLI
```

## 🔧 Troubleshooting

### Common Issues

#### `ffmpeg not found`
**Solution:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Verify
ffmpeg -version
```

#### `OPENAI_API_KEY not set`
**Solution:**
```bash
# Option 1: Use --api-key flag (persists to keyring)
lazy-prompt --api-key sk-proj-your-key

# Option 2: Set environment variable
export OPENAI_API_KEY="sk-proj-your-key"

# Option 3: Create .env file
echo 'OPENAI_API_KEY="sk-proj-your-key"' > .env
```

#### `No speech detected`
**Possible causes:**
- Microphone not selected as default input
- Speaking too quietly
- Background noise interference

**Solution:**
```bash
# Check microphone permissions (macOS)
System Preferences → Security & Privacy → Microphone

# Test microphone
python -c "import sounddevice as sd; print(sd.query_devices())"
```

#### `Permission denied: keyring`
**Solution:**
Keyring storage is optional. If it fails, use environment variables:
```bash
export OPENAI_API_KEY="sk-proj-your-key"
```

#### Import errors after installation
**Solution:**
```bash
# Reinstall in clean environment
pip uninstall lazy-prompt
pip install --no-cache-dir git+https://github.com/Mohit4Maq/speaking-my-prompt.git
```

### Getting Help

- **Issues:** [GitHub Issues](https://github.com/Mohit4Maq/speaking-my-prompt/issues)
- **Discussions:** [GitHub Discussions](https://github.com/Mohit4Maq/speaking-my-prompt/discussions)

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

**Quick start for contributors:**

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/speaking-my-prompt.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make changes and test locally
5. Commit: `git commit -m "Add: your feature description"`
6. Push: `git push origin feature/your-feature-name`
7. Open a Pull Request

**Development setup:**
```bash
# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Format code
black src/
ruff check src/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**MIT License Summary:**
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Private use
- ❌ Liability
- ❌ Warranty

## 🚀 Future Enhancements

### High Priority

- [ ] **Real-time streaming transcription** - Display text as you speak
  - Use Whisper API's streaming capabilities
  - Show live word-by-word updates
  - Reduce latency for immediate feedback

- [ ] **Custom prompt templates** - Save and reuse prompt structures
  - Template library (code review, meeting notes, brainstorming)
  - Variable substitution in templates
  - Template sharing via GitHub

- [ ] **Multi-speaker detection** - Identify different speakers
  - Use pyannote.audio for diarization
  - Label speakers in transcript
  - Export speaker-separated segments

### Medium Priority

- [ ] **Web interface** - Browser-based UI for non-CLI users
  - Built with Flask/FastAPI
  - Drag-and-drop audio upload
  - Real-time progress tracking

- [ ] **Audio preprocessing improvements**
  - Noise reduction (noisereduce library)
  - Volume normalization
  - Echo cancellation

- [ ] **Output format options**
  - Export to Markdown, JSON, CSV, SRT (subtitles)
  - Notion API integration
  - Slack/Discord webhook support

- [ ] **Voice commands** - Control via speech
  - "Save this transcript"
  - "Translate to Spanish"
  - "Enhance this prompt"

### Low Priority

- [ ] **Offline mode** - Use local Whisper model
  - Download and cache model
  - Fallback when API unavailable
  - Privacy-focused mode

- [ ] **Meeting minutes enhancements**
  - Action item extraction with assignees
  - Decision tracking
  - Follow-up reminders

- [ ] **Mobile app** - iOS/Android companion
  - Record on phone, process on server
  - Push notifications when ready
  - Sync with cloud storage

- [ ] **Performance optimizations**
  - Parallel processing for large files
  - Chunk-based streaming for long recordings
  - Caching for repeated requests

### Research & Experimental

- [ ] **Fine-tuned models** - Domain-specific accuracy
  - Medical transcription
  - Legal terminology
  - Technical jargon

- [ ] **Multi-modal input** - Combine audio + video + screen
  - Screen recording with narration
  - Slide deck + presentation audio
  - Video call transcription

- [ ] **AI-powered summarization** - Beyond transcription
  - Key points extraction
  - Sentiment analysis
  - Topic clustering

### Community Requests

Have an idea? [Open an issue](https://github.com/Mohit4Maq/speaking-my-prompt/issues/new) with the label `enhancement`!

---

## 📊 Stats

- **Version:** 0.1.4
- **Python:** 3.10+
- **Languages:** 100+
- **License:** MIT

## 🙏 Acknowledgments

- **OpenAI** - Whisper API and GPT-4
- **Contributors** - Thank you to all contributors!
- **Community** - For feedback and feature requests

---

**Built with ❤️ by [Mohit Chand](https://github.com/Mohit4Maq)**
