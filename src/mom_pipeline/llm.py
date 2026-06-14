"""Shared OpenAI client helpers for the project.

Centralizes client construction and wraps calls in the existing
``mom_pipeline.utils.Retry`` so transient rate-limit/network errors don't abort
live sessions.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .utils import Retry

CHAT_MODEL = "gpt-4o"
EMBED_MODEL = "text-embedding-3-small"

_RETRY = Retry(attempts=3, base_delay=1.0, max_delay=8.0)


def get_client(api_key: Optional[str] = None) -> OpenAI:
    """Construct an OpenAI client, honoring an explicit key or env config."""
    return OpenAI(api_key=api_key) if api_key else OpenAI()


def chat_json(
    client: OpenAI,
    system: str,
    user: str,
    model: str = CHAT_MODEL,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """Call chat completions in JSON mode and return the parsed object.

    Returns ``{}`` if the model emits unparseable content (callers schema-fill).
    """

    def _call() -> str:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or "{}"

    content = _RETRY.run(_call)
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {}


def chat_text(
    client: OpenAI,
    system: str,
    user: str,
    model: str = CHAT_MODEL,
    temperature: float = 0.5,
) -> str:
    """Call chat completions and return the plain text reply (stripped)."""

    def _call() -> str:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    return _RETRY.run(_call).strip()


def embed(client: OpenAI, texts: List[str], model: str = EMBED_MODEL) -> List[List[float]]:
    """Embed a batch of texts; returns one vector per input."""

    def _call():
        return client.embeddings.create(model=model, input=texts)

    resp = _RETRY.run(_call)
    return [item.embedding for item in resp.data]
