# Contributing to Lazy Prompt

Thank you for considering contributing to Lazy Prompt! This document provides guidelines and instructions for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of background, identity, or experience level.

### Expected Behavior

- Be respectful and considerate in all interactions
- Use welcoming and inclusive language
- Accept constructive criticism gracefully
- Focus on what's best for the community
- Show empathy towards other contributors

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Trolling, insulting, or derogatory remarks
- Publishing others' private information without permission
- Any conduct that could reasonably be considered inappropriate

## How Can I Contribute?

### Reporting Bugs

**Before submitting a bug report:**
- Check the [existing issues](https://github.com/Mohit4Maq/speaking-my-prompt/issues) to avoid duplicates
- Verify the bug exists in the latest version
- Collect relevant information (OS, Python version, error messages)

**Submitting a bug report:**
1. Go to [GitHub Issues](https://github.com/Mohit4Maq/speaking-my-prompt/issues/new)
2. Use a clear, descriptive title
3. Provide detailed steps to reproduce the issue
4. Include error messages, logs, and screenshots if applicable
5. Describe expected vs actual behavior
6. Add label: `bug`

**Bug report template:**
```markdown
**Environment:**
- OS: macOS 13.5
- Python version: 3.10.5
- Package version: 0.1.4

**Steps to reproduce:**
1. Run `lazy-prompt --language en`
2. Speak for 10 seconds
3. Press Ctrl+C

**Expected behavior:**
Transcript should be copied to clipboard

**Actual behavior:**
Error: "Clipboard copy failed"

**Error log:**
```
[paste error message here]
```

**Additional context:**
[Any other relevant information]
```

### Suggesting Enhancements

**Before submitting an enhancement:**
- Check if the feature already exists
- Review [existing feature requests](https://github.com/Mohit4Maq/speaking-my-prompt/labels/enhancement)
- Consider if it aligns with project goals

**Submitting an enhancement:**
1. Open a new issue with label `enhancement`
2. Provide a clear use case and rationale
3. Describe proposed implementation (if applicable)
4. Include examples or mockups

### Code Contributions

We welcome code contributions! Here's how to get started:

1. **Fork the repository**
2. **Create a feature branch** (see naming conventions below)
3. **Make your changes**
4. **Test thoroughly**
5. **Submit a pull request**

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- ffmpeg (for audio processing)

### Local Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/speaking-my-prompt.git
cd speaking-my-prompt

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install in editable mode with development dependencies
pip install -e ".[dev]"

# 4. Install pre-commit hooks (if available)
pre-commit install

# 5. Create .env file with your API key
echo 'OPENAI_API_KEY="sk-proj-your-key-here"' > .env

# 6. Verify installation
lazy-prompt --help
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_cli.py

# Run with verbose output
pytest -v tests/
```

### Code Formatting

We use `black` and `ruff` for code formatting and linting:

```bash
# Format code
black src/ tests/

# Check linting
ruff check src/ tests/

# Auto-fix linting issues
ruff check --fix src/ tests/
```

## Coding Standards

### Python Style Guide

- Follow [PEP 8](https://pep8.org/) conventions
- Use `black` for automatic formatting (line length: 100)
- Use type hints for function signatures
- Write descriptive variable and function names

### Code Quality

- **DRY (Don't Repeat Yourself):** Avoid code duplication
- **KISS (Keep It Simple, Stupid):** Prefer simple, clear solutions
- **YAGNI (You Aren't Gonna Need It):** Don't add unnecessary features
- **Single Responsibility:** Each function should do one thing well

### Type Hints

```python
# Good
def transcribe_audio(audio_bytes: bytes, language: str = "en") -> tuple[str, list[dict]]:
    """Transcribe audio using Whisper API."""
    pass

# Bad
def transcribe_audio(audio_bytes, language="en"):
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
        
    Examples:
        >>> calculate_average([1, 2, 3, 4, 5])
        3.0
    """
    if not numbers:
        raise ValueError("Cannot calculate average of empty list")
    return sum(numbers) / len(numbers)
```

### Error Handling

- Use specific exception types
- Provide helpful error messages
- Log errors appropriately

```python
# Good
try:
    result = transcribe_audio(audio_bytes, language="en")
except openai.APIError as e:
    logger.error(f"OpenAI API error: {e}")
    raise RuntimeError(f"Transcription failed: {e}") from e

# Bad
try:
    result = transcribe_audio(audio_bytes, language="en")
except Exception as e:
    print("Error")
```

## Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, no logic change)
- `refactor:` Code refactoring (no functional change)
- `test:` Adding or updating tests
- `chore:` Maintenance tasks (dependencies, config)
- `perf:` Performance improvements
- `ci:` CI/CD changes

### Examples

```bash
# Feature
feat(cli): add --enhance-prompt flag for GPT-4 enhancement

# Bug fix
fix(transcribe): handle empty audio input gracefully

# Documentation
docs(readme): update installation instructions for Windows

# Refactor
refactor(cli): extract API key handling into separate function

# Multiple files
feat(cli,transcribe): add multi-language translation support
```

### Subject Line

- Use imperative mood ("add" not "added" or "adds")
- Don't capitalize first letter
- No period at the end
- Keep under 72 characters

### Body (optional)

- Provide context and motivation for the change
- Explain "why" not "what" (code shows what)
- Wrap at 72 characters

### Footer (optional)

- Reference issues: `Closes #123` or `Fixes #456`
- Breaking changes: `BREAKING CHANGE: <description>`

## Pull Request Process

### Before Submitting

- [ ] Code follows project style guidelines
- [ ] All tests pass (`pytest tests/`)
- [ ] New tests added for new functionality
- [ ] Documentation updated (README, docstrings)
- [ ] Commit messages follow conventions
- [ ] No merge conflicts with `main` branch

### Branch Naming

Use descriptive branch names:

- `feature/prompt-enhancement` - New feature
- `fix/clipboard-error` - Bug fix
- `docs/contributing-guide` - Documentation
- `refactor/api-key-handling` - Code refactoring

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to break)
- [ ] Documentation update

## Testing
Describe how you tested your changes

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added/updated
- [ ] All tests pass locally

## Related Issues
Closes #123
```

### Review Process

1. **Automated checks** run on all PRs (linting, tests)
2. **Maintainer review** within 48 hours
3. **Feedback addressed** by contributor
4. **Approval** by at least one maintainer
5. **Merge** by maintainer (squash and merge)

### After Merge

- Delete your branch
- Update your fork with latest `main`
- Celebrate your contribution! 🎉

## Testing Guidelines

### Test Structure

```python
# tests/test_cli.py
import pytest
from lazy_prompt.cli import run_once

def test_run_once_basic():
    """Test basic voice transcription workflow."""
    # Arrange
    output_dir = Path("/tmp/test")
    
    # Act
    result = run_once(output_dir, language="en")
    
    # Assert
    assert result == 0
    assert output_dir.exists()
```

### Test Coverage

- Aim for >80% code coverage
- Test edge cases and error conditions
- Use mocking for external API calls

```python
from unittest.mock import patch, MagicMock

@patch('lazy_prompt.cli.OpenAI')
def test_transcribe_with_mock(mock_openai):
    """Test transcription with mocked API."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.audio.transcriptions.create.return_value.text = "Hello world"
    
    result = transcribe_audio(b"fake_audio")
    assert result == "Hello world"
```

## Documentation

### README Updates

- Update README.md for user-facing changes
- Include examples for new features
- Update troubleshooting section for common issues

### Code Comments

- Explain "why" not "what" (code should be self-explanatory)
- Use comments for complex algorithms or business logic
- Keep comments up-to-date with code changes

### CHANGELOG

- Add entry to CHANGELOG.md for each release
- Group changes by type (Features, Bug Fixes, etc.)
- Include issue/PR references

## Getting Help

### Questions?

- **Discussions:** [GitHub Discussions](https://github.com/Mohit4Maq/speaking-my-prompt/discussions)
- **Chat:** (Add Discord/Slack if available)

### Resources

- [Python Style Guide (PEP 8)](https://pep8.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)

---

## Recognition

Contributors are recognized in:
- GitHub contributors page
- CHANGELOG.md (for significant contributions)
- README.md acknowledgments section

Thank you for contributing to Lazy Prompt! 🙏
