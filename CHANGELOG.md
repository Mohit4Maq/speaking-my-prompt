# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Real-time streaming transcription
- Custom prompt templates
- Multi-speaker detection
- Web interface

## [0.1.4] - 2026-01-03

### Changed
- **BREAKING:** Changed default behavior to clipboard-only (no files saved by default)
- Replaced `--no-save` flag with `--save` flag
- Updated help text to reflect new default behavior

### Improved
- Documentation: Updated README with new default behavior
- User experience: Reduced clutter by not saving files unless explicitly requested

## [0.1.3] - 2026-01-03

### Added
- GPT-4 prompt enhancement feature (`--enhance-prompt` flag)
- Expert-level prompt engineering system for transforming casual speech
- Enhanced prompt output saved to `enhanced_prompt.txt` when `--save` is used

### Improved
- Documentation: Added examples of GPT-4 prompt enhancement
- CLI help text: Added description for `--enhance-prompt` flag

## [0.1.2] - 2026-01-02

### Added
- Translation support (`--translate-to-english` flag)
- Multi-language transcription with auto-translation to English
- Support for Whisper's translations endpoint

### Fixed
- Removed unsupported `language` parameter from translations API call
- Fixed translation endpoint to auto-detect source language

### Improved
- Language support documentation in README
- Error handling for translation failures

## [0.1.1] - 2026-01-02

### Added
- API key persistence using `keyring` library
- `--api-key` flag to set and persist OpenAI API key
- OS-level secure storage (macOS Keychain, Windows Credential Manager)
- Fallback to environment variables if keyring fails

### Changed
- Import paths: Changed from `src.mom_pipeline` to `mom_pipeline` for proper package installation
- Package structure: Moved CLI to `src/lazy_prompt/cli.py`

### Fixed
- Import errors when installing via pip
- Module resolution issues in editable installs

### Improved
- First-time user experience with API key setup
- Security: API keys stored in OS keyring instead of plaintext
- Documentation: Added API key persistence instructions

## [0.1.0] - 2026-01-01

### Added
- Initial release of `lazy-prompt` package
- Live voice recording via microphone
- OpenAI Whisper API transcription
- Clipboard integration with `pyperclip`
- Language selection (`--language` flag)
- Optional file saving (`--no-save` flag)
- Console script entrypoint (`lazy-prompt` command)
- Basic CLI with argparse
- Audio preprocessing (noise reduction, normalization)
- Timestamped segments in JSON output
- Metadata tracking (duration, processing time)

### Features
- Python 3.10+ support
- 100+ language support via Whisper
- Cross-platform compatibility (macOS, Linux, Windows)
- Virtual environment isolation support
- Git-based installation from GitHub

### Documentation
- README.md with installation and usage instructions
- Requirements.txt with dependencies
- pyproject.toml for package metadata
- Example .env file template

### Dependencies
- openai >= 1.0.0
- requests >= 2.31.0
- tqdm >= 4.66.0
- python-dateutil >= 2.8.2
- python-dotenv >= 1.0.0
- watchdog >= 3.0.0
- sounddevice >= 0.4.6
- scipy >= 1.11.0
- pyperclip >= 1.8.2

## [0.0.1] - 2025-12-28

### Initial Development
- Prototype voice capture module
- Initial Whisper API integration testing
- Proof of concept for clipboard integration

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| 0.1.4 | 2026-01-03 | Clipboard-only default, `--save` flag |
| 0.1.3 | 2026-01-03 | GPT-4 prompt enhancement |
| 0.1.2 | 2026-01-02 | Translation support |
| 0.1.1 | 2026-01-02 | API key persistence with keyring |
| 0.1.0 | 2026-01-01 | Initial release |

---

## Legend

- **Added:** New features
- **Changed:** Changes to existing functionality
- **Deprecated:** Soon-to-be removed features
- **Removed:** Removed features
- **Fixed:** Bug fixes
- **Security:** Security improvements
- **Breaking:** Breaking changes requiring user action

---

[Unreleased]: https://github.com/Mohit4Maq/speaking-my-prompt/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/Mohit4Maq/speaking-my-prompt/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Mohit4Maq/speaking-my-prompt/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Mohit4Maq/speaking-my-prompt/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Mohit4Maq/speaking-my-prompt/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Mohit4Maq/speaking-my-prompt/releases/tag/v0.1.0
[0.0.1]: https://github.com/Mohit4Maq/speaking-my-prompt/releases/tag/v0.0.1
