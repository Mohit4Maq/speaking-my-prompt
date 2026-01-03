#!/usr/bin/env python3
"""Manual end-to-end test for interactive mode with mocked OpenAI calls."""
import subprocess
import sys
from pathlib import Path

# Test data: simulate what a user would input
# Choice 1 = text mode, then provide prompt, then "1" to continue, "C" to complete
test_input = """2
Create a machine learning model to classify images
1
I need to use a pre-trained model like ResNet or VGG
The model should handle different image sizes
I want to train it on my custom dataset
C
"""

def test_interactive_cli():
    """Test the CLI interactive mode end-to-end."""
    venv_python = Path.home() / "Python/speech_text/.venv/bin/python"
    
    try:
        proc = subprocess.Popen(
            [str(venv_python), "-m", "lazy_prompt.cli", "--interactive", "--language", "en"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path.home() / "Python/speech_text"),
        )
        
        # Run with timeout
        stdout, stderr = proc.communicate(input=test_input, timeout=10)
        
        # Check output
        print("=" * 70)
        print("STDOUT:")
        print("=" * 70)
        print(stdout[:2000])  # Print first 2000 chars
        
        if stderr:
            print("\n" + "=" * 70)
            print("STDERR:")
            print("=" * 70)
            print(stderr[:500])
        
        # Verify expected output patterns
        checks = [
            ("Interactive Refinement" in stdout, "Interactive mode started"),
            ("Choice (1/2)" in stdout or "Speak or" in stdout, "Input prompt selection shown"),
            ("OpenAI API key" not in stderr, "No missing API key errors"),
        ]
        
        print("\n" + "=" * 70)
        print("VALIDATION:")
        print("=" * 70)
        for check, desc in checks:
            status = "✓" if check else "✗"
            print(f"{status} {desc}")
        
        return all(check for check, _ in checks)
        
    except subprocess.TimeoutExpired:
        print("❌ Test timed out - CLI may be waiting for real audio input")
        proc.kill()
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_interactive_cli()
    sys.exit(0 if success else 1)
