"""interview_eval: live interview evaluation tool (Whisper + GPT-4o).

Captures both sides of a Google Meet call via a macOS Aggregate Device
(interviewer mic on one channel, candidate audio on another), transcribes
each utterance, matches it to a pre-loaded question bank, and scores the
candidate's answers against competencies parsed from a job description.
"""

__version__ = "0.1.0"
