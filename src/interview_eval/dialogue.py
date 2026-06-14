"""Adaptive follow-up question generation for the AI interviewer.

Given the current question and the candidate's answer so far, produce ONE concise
spoken follow-up that probes a gap or asks for a concrete example. Kept short and
conversational because it will be read aloud (OpenAI TTS) to the candidate.
"""
from __future__ import annotations

from typing import Optional

from mom_pipeline.llm import chat_text, get_client

_SYSTEM = """You are a senior technical interviewer conducting a live interview.
Given the question you asked and the candidate's answer so far, ask ONE short,
natural follow-up question that digs deeper, probes a gap, or asks for a concrete
example. It will be spoken aloud, so keep it to a single conversational sentence.
Return ONLY the follow-up question text — no preamble, no quotes, no numbering."""


def generate_followup(
    question: str,
    answer: str,
    role_title: str = "",
    api_key: Optional[str] = None,
    client=None,
) -> str:
    """Return a single spoken follow-up question for the given Q/A so far."""
    client = client or get_client(api_key)
    user = (
        f"Role: {role_title or 'N/A'}\n"
        f"Question asked: {question}\n"
        f"Candidate's answer so far: {answer or '(no answer yet)'}\n\n"
        "Ask one short follow-up question."
    )
    return chat_text(client, _SYSTEM, user, temperature=0.6)
