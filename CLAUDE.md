# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lazy Prompt** is a voice-to-text CLI tool that transforms spoken input into polished, structured prompts using OpenAI Whisper (transcription) and GPT-4 (enhancement). The tool supports 100+ languages, hands-free operation, interactive refinement, and seamless clipboard integration.

**Main CLI command:** `lazy-prompt`

## Development Setup

### Prerequisites
- Python 3.10+
- ffmpeg (required for audio processing)
- OpenAI API key

### Installation
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .

# With dev dependencies
pip install -e ".[dev]"

# Verify installation
lazy-prompt --help
```

### Environment Configuration
```bash
# Set API key (stored in OS keyring)
lazy-prompt --api-key sk-proj-your-key-here

# Or use environment variable
export OPENAI_API_KEY="sk-proj-your-key"

# Or create .env file
echo 'OPENAI_API_KEY="sk-proj-your-key"' > .env
```

## Common Commands

### Running the CLI
```bash
# Basic voice-to-text (English)
lazy-prompt --language en

# With GPT-4 prompt enhancement
lazy-prompt --enhance-prompt --language en

# Interactive refinement mode (hands-free with AI dialogue)
lazy-prompt --interactive --language en

# Multi-language with translation
lazy-prompt --language hi --translate-to-english

# Save outputs to disk (default: clipboard only)
lazy-prompt --save --output-dir ~/my-prompts

# Disable clipboard copy
lazy-prompt --no-clipboard --save
```

### Testing
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run specific test
pytest tests/test_cli.py

# Verbose output
pytest -v tests/
```

### Code Quality
```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Auto-fix linting issues
ruff check --fix src/ tests/
```

## Architecture

### Package Structure
- **`src/lazy_prompt/`** - Main CLI package
  - `cli.py` - CLI entrypoint (`lazy-prompt` command)
  - `interactive.py` - Interactive refinement with AI dialogue and hands-free TTS

- **`src/mom_pipeline/`** - Core audio/transcription modules
  - `live_capture.py` - Audio capture with auto-stop silence detection
  - `live_transcribe.py` - Whisper API integration (transcribe/translate)
  - `transcribe.py` - File-based transcription
  - `intake.py` - Audio file validation and format conversion
  - `postprocess.py` - Text cleanup and normalization
  - `mom_generate.py` - Meeting minutes generation (GPT-4)
  - `watcher.py` - Folder monitoring for file-based workflows
  - `config.py` - Configuration management
  - `utils.py` - Shared utilities

- **Root scripts** (legacy/standalone)
  - `live_transcribe_only.py` - Standalone transcription script
  - `live_voice_mom.py` - Meeting minutes workflow
  - `mom_cli.py` - File processing CLI
  - `gui_app.py` - Optional GUI application
  - `setup.py` - py2app configuration for macOS app bundle

### Audio Processing Flow

1. **Capture** (`live_capture.py`)
   - `stream_audio()` - Manual capture (Ctrl+C to stop)
   - `stream_audio_auto_stop()` - Hands-free with silence detection
   - Audio preprocessing: noise reduction, normalization, resampling

2. **Transcription** (`live_transcribe.py`)
   - `transcribe_audio()` - Whisper API with segment-level timing
   - `translate_audio()` - Translate to English from any language
   - Returns: (full_text, segments) tuple

3. **Enhancement** (`cli.py`, `interactive.py`)
   - **Standard**: `_enhance_prompt()` - GPT-4 one-shot enhancement
   - **Interactive**: `interactive_refinement_flow()` - Multi-turn dialogue with clarifying questions
   - Uses GPT-4o model for conversational prompts

4. **Output** (`cli.py`)
   - Default: Copy to clipboard (pyperclip)
   - Optional: Save audio, transcript, segments, metadata to disk

### Interactive Mode ("Jarvis Mode")

The interactive refinement flow (`--interactive`) implements a hands-free conversational AI:

1. **Initial capture** - Auto-starts voice recording, stops after silence
2. **AI dialogue** - GPT-4 asks clarifying questions (spoken via macOS `say`)
3. **User responses** - Captured via voice, transcribed with Whisper
4. **Iterative refinement** - Continues until user says "DONE" or similar
5. **Final prompt generation** - Produces developer-ready system specification

**Key features:**
- Wake phrase support: "Hey Jarvis" (stripped from final prompt)
- Text-to-speech feedback using macOS `say` command
- Multi-turn conversation history maintained for context
- Specialized system prompt for developer/system-spec output

### API Key Management

**Priority order:**
1. `--api-key` CLI argument (persists to keyring)
2. `OPENAI_API_KEY` environment variable
3. Keyring storage (macOS Keychain, Windows Credential Manager)

**Keyring service:** `lazy-prompt`
**Keyring username:** `OPENAI_API_KEY`

### Output Modes

**Clipboard-only (default):**
- No files saved to disk
- Transcript copied immediately
- Minimal footprint

**Save mode (`--save`):**
- `audio_original.wav` - Original recording
- `transcript.txt` - Raw Whisper output
- `enhanced_prompt.txt` - GPT-4 enhanced (if `--enhance-prompt` or `--interactive`)
- `transcript_segments.json` - Timestamped segments
- `metadata.json` - Processing metrics (duration, API usage, etc.)

## Code Conventions

### Type Hints
Use type hints for all function signatures:
```python
from typing import Tuple, List, Dict, Optional

def transcribe_audio(audio_bytes: bytes, language: str = "en") -> Tuple[str, List[Dict]]:
    """Transcribe audio with Whisper API."""
    pass
```

### Docstrings
Use Google-style docstrings:
```python
def calculate_average(numbers: list[float]) -> float:
    """Calculate the arithmetic mean of a list of numbers.

    Args:
        numbers: List of numerical values to average.

    Returns:
        The arithmetic mean as a float.

    Raises:
        ValueError: If the input list is empty.
    """
```

### Error Handling
- Use specific exception types
- Provide helpful error messages
- Avoid broad `except Exception` unless logging/re-raising

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```bash
feat(cli): add --interactive flag for AI-guided refinement
fix(transcribe): handle empty audio input gracefully
docs(readme): update installation for Windows
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`

## Testing Strategy

### Mock External APIs
Always mock OpenAI API calls in tests:
```python
from unittest.mock import patch, MagicMock

@patch('lazy_prompt.cli.OpenAI')
def test_transcribe_with_mock(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.audio.transcriptions.create.return_value.text = "Test output"

    result = transcribe_audio(b"fake_audio")
    assert result == "Test output"
```

### Test Coverage
- Aim for >80% coverage
- Test edge cases (empty audio, API errors, silence detection)
- Use fixtures for common test data (sample audio bytes)

## Platform-Specific Notes

### macOS
- Uses `say` command for TTS in interactive mode
- Keyring storage via macOS Keychain
- `.app` bundle creation with `py2app` (see `setup.py`, `scripts/build_app.sh`)

### Windows
- Requires ffmpeg installation via Chocolatey
- Keyring storage via Windows Credential Manager
- TTS not supported (interactive mode degrades gracefully)

### Linux
- ffmpeg via apt-get
- Keyring support depends on installation (may fail silently)
- No TTS support

## Key Dependencies

- **openai** - Whisper API, GPT-4 API
- **sounddevice** - Real-time audio capture
- **scipy** - Audio preprocessing and WAV file handling
- **pyperclip** - Cross-platform clipboard integration
- **keyring** - Secure API key storage
- **python-dotenv** - Environment variable management
- **watchdog** - File system monitoring (legacy workflows)

## Related Scripts

- **`.voice_alias.sh`** - Bash alias for quick `voice` command (see VOICE_COPILOT.md)
- **`live_transcribe_only.py`** - Standalone script without CLI framework
- **`mom_cli.py`** - Batch processing for audio files (meeting minutes)

## Troubleshooting

### Common Issues

**ffmpeg not found:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Verify
ffmpeg -version
```

**No speech detected:**
- Check microphone permissions (System Preferences → Security & Privacy → Microphone on macOS)
- Test microphone: `python -c "import sounddevice as sd; print(sd.query_devices())"`
- Adjust silence threshold in `stream_audio_auto_stop()` parameters

**Clipboard copy fails:**
- Keyring/clipboard libraries may fail on headless systems
- Use `--no-clipboard --save` for CI/CD environments

**API key not persisted:**
- Keyring storage is optional and may fail silently
- Fallback: Use environment variables or `.env` file

## Future Enhancements

See README.md "Future Enhancements" section for roadmap. High-priority items:
- Real-time streaming transcription (word-by-word display)
- Custom prompt templates (save/reuse structures)
- Multi-speaker detection (pyannote.audio)
- Web interface (Flask/FastAPI)
