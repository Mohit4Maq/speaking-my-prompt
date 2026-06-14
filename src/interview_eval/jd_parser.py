"""Parse a job description into weighted, scoreable competencies.

GPT-4o (JSON mode, temperature 0) extracts 4-8 competencies from the JD, each
with a relative ``weight``, a ``description``, and observable ``signals`` the
scorer looks for. Weights are normalized to sum to 1.0. The result is cached to
``competencies.json`` so weights can be hand-tuned and reused across sessions.

Mirrors the schema-completion pattern in ``mom_pipeline.mom_generate.generate_mom``.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from mom_pipeline.utils import safe_json_dump

from mom_pipeline.llm import get_client, chat_json

_SYSTEM = """You are an expert technical recruiter and hiring rubric designer.
Given a job description, extract the 4-8 core competencies a candidate should be
evaluated on. For each competency provide:
- id: short kebab-case slug (e.g. "system-design")
- name: human-readable name
- weight: relative importance as a number (you choose; they need not sum to 1)
- description: one sentence on what strong performance looks like
- signals: 2-5 concrete, observable things an interviewer should listen for

Return strict JSON:
{"role_title": string,
 "competencies": [{"id": str, "name": str, "weight": number,
                   "description": str, "signals": [str, ...]}, ...]}
Base everything ONLY on the job description. Do not invent unrelated skills."""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "competency"


def _to_float(value: Any, default: float = 1.0) -> float:
    """Safely convert a value to float, returning default on failure."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def normalize_weights(competencies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return competencies with ``weight`` rescaled to sum to 1.0 (even split if all zero)."""
    total = sum(max(_to_float(c.get("weight")), 0.0) for c in competencies)
    n = len(competencies)
    if n == 0:
        return competencies
    for c in competencies:
        w = max(_to_float(c.get("weight")), 0.0)
        c["weight"] = (w / total) if total > 0 else (1.0 / n)
    return competencies


def parse_jd(jd_text: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Parse JD text into ``{role_title, competencies:[...]}`` with normalized weights."""
    client = get_client(api_key)
    data = chat_json(client, _SYSTEM, jd_text, temperature=0.0)

    competencies = data.get("competencies") or []
    cleaned: List[Dict[str, Any]] = []
    seen_ids = set()
    for c in competencies:
        if not isinstance(c, dict) or not (c.get("name") or c.get("id")):
            continue
        cid = _slugify(str(c.get("id") or c.get("name")))
        while cid in seen_ids:
            cid += "-x"
        seen_ids.add(cid)
        cleaned.append(
            {
                "id": cid,
                "name": str(c.get("name") or cid),
                "weight": _to_float(c.get("weight")),
                "description": str(c.get("description", "")),
                "signals": [str(s) for s in (c.get("signals") or [])],
            }
        )
    cleaned = normalize_weights(cleaned)
    return {"role_title": str(data.get("role_title", "")), "competencies": cleaned}


def load_or_parse(
    jd_path: str,
    cache_path: str,
    force: bool = False,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Return cached competencies if present, else parse the JD and cache the result.

    Set ``force=True`` (``--reparse-jd``) to re-parse and overwrite the cache.
    """
    if not force and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()
    parsed = parse_jd(jd_text, api_key=api_key)
    safe_json_dump(parsed, cache_path)
    return parsed
