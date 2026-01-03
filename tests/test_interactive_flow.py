"""Test the interactive refinement flow without requiring real voice input."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lazy_prompt.interactive import (
    interactive_dialogue_session,
    generate_refined_prompt,
    interactive_refinement_flow,
)


def test_interactive_refinement_flow_with_mocked_audio():
    """Test the full interactive refinement flow with mocked audio."""
    
    # Mock audio capture and transcription
    with patch("lazy_prompt.interactive.stream_audio_auto_stop") as mock_stream, \
         patch("lazy_prompt.interactive.transcribe_audio") as mock_transcribe, \
         patch("lazy_prompt.interactive.OpenAI") as mock_openai_class, \
         patch("lazy_prompt.interactive._speak_text") as mock_tts:
        
        # Setup mock audio capture
        mock_stream.return_value = b"mock_audio_data"
        
        # Setup mock transcription for dialogue turns
        # Turn 1: user answer, Turn 2: user says DONE
        mock_transcribe.side_effect = [
            ("I need to build a machine learning classifier for images", ["I need to build a machine learning classifier for images"]),
            ("DONE", ["DONE"]),
        ]
        
        # Setup mock OpenAI responses
        mock_client = MagicMock()
        
        # First response: AI asks follow-up questions
        response1 = MagicMock()
        response1.choices[0].message.content = """Great! Let me ask some clarifying questions:

1. What types of images will you be classifying?
2. Do you want to use a pre-trained model?"""
        
        # Second response: More questions
        response2 = MagicMock()
        response2.choices[0].message.content = "What's your timeline?"
        
        # Third response: Final refined prompt
        response3 = MagicMock()
        response3.choices[0].message.content = """# Image Classification ML Model

## Objective
Build a machine learning classifier to categorize images.

## Requirements
- Support multiple image formats
- Use pre-trained model
- Model accuracy > 90%"""
        
        mock_client.chat.completions.create.side_effect = [response1, response2, response3]
        mock_openai_class.return_value = mock_client
        
        # Run the flow
        initial_prompt = "I want to build an image classifier"
        result = interactive_refinement_flow(
            initial_prompt,
            language="en",
            api_key="test-api-key"
        )
        
        # Verify results
        assert "Image Classification" in result or "Objective" in result
        assert mock_stream.called
        assert mock_transcribe.called
        assert mock_client.chat.completions.create.called
        mock_tts.assert_called()


def test_interactive_dialogue_session_basic():
    """Test the interactive dialogue session with mocked input."""
    
    with patch("lazy_prompt.interactive.stream_audio_auto_stop") as mock_stream, \
         patch("lazy_prompt.interactive.transcribe_audio") as mock_transcribe, \
         patch("lazy_prompt.interactive.OpenAI") as mock_openai_class, \
         patch("lazy_prompt.interactive._speak_text") as mock_tts:
        
        mock_stream.return_value = b"mock_audio"
        # First transcription: user's answer, Second: user says DONE
        mock_transcribe.side_effect = [
            ("I need a REST API", ["I need a REST API"]),
            ("DONE", ["DONE"]),
        ]
        
        # Mock AI's follow-up questions and response
        mock_client = MagicMock()
        response1 = MagicMock()
        response1.choices[0].message.content = "What database do you want to use?"
        response2 = MagicMock()
        response2.choices[0].message.content = "What authentication method?"
        
        mock_client.chat.completions.create.side_effect = [response1, response2]
        mock_openai_class.return_value = mock_client
        
        history, combined_text = interactive_dialogue_session(
            initial_prompt="Build an API",
            language="en",
            api_key="test-key"
        )
        
        # Check the combined transcript contains user inputs
        assert "API" in combined_text
        assert "DONE" in combined_text
        # Check the history contains conversation turns
        assert len(history) > 0
        assert history[0]["role"] == "system"
        mock_tts.assert_called()


def test_generate_refined_prompt():
    """Test the refined prompt generation function."""
    
    with patch("lazy_prompt.interactive.OpenAI") as mock_openai_class:
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "# Refined Prompt\n\nYour detailed prompt here..."
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Create a simple conversation history
        conversation = [
            {"role": "system", "content": "You are a prompt engineer"},
            {"role": "user", "content": "I need a REST API"},
            {"role": "assistant", "content": "What database will you use?"},
            {"role": "user", "content": "PostgreSQL"}
        ]
        
        result = generate_refined_prompt(
            conversation,
            "I need a REST API. PostgreSQL",
            api_key="test-key"
        )
        
        assert "Refined Prompt" in result
        assert mock_client.chat.completions.create.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
