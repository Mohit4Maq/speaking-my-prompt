"""Score a candidate's answer against the active question's competencies.

GPT-4o (JSON mode, low temperature) rates an answer 1-10 and must ground every
score in evidence quoted from the answer transcript — this reduces hallucinated
praise/criticism and keeps scores defensible. Designed as a pure function so it
is trivially unit-tested with a mocked client.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mom_pipeline.llm import get_client, chat_json

_SYSTEM = """You are a rigorous, fair technical interviewer scoring one answer.
Score ONLY on the evidence in the answer transcript. Do not reward fluency over
substance, and do not penalize an answer for not covering things that weren't
asked. Every score MUST be backed by a short quote from the answer.

Return strict JSON:
{"score": integer 1-10 (overall for this answer),
 "per_competency": {competency_id: integer 1-10, ...},
 "evidence_quotes": [short verbatim quotes from the answer, ...],
 "strengths": [str, ...],
 "gaps": [str, ...],
 "rationale": one or two sentences}
If the answer is empty or non-responsive, score low and say so in rationale.
Use only the provided competency ids as keys in per_competency."""

# Schema keys we guarantee in the returned dict.
_LIST_KEYS = ("evidence_quotes", "strengths", "gaps")


def _build_user_prompt(
    question: str,
    answer: str,
    competencies: List[Dict[str, Any]],
    role_title: str,
) -> str:
    comp_lines = []
    for c in competencies:
        signals = "; ".join(c.get("signals", []))
        comp_lines.append(
            f"- {c['id']} ({c.get('name', c['id'])}): {c.get('description', '')}"
            + (f" Signals: {signals}" if signals else "")
        )
    comp_block = "\n".join(comp_lines) if comp_lines else "- (no specific competencies; judge general quality)"
    return (
        f"Role: {role_title or 'N/A'}\n\n"
        f"Question asked:\n{question}\n\n"
        f"Competencies to assess (use these ids as per_competency keys):\n{comp_block}\n\n"
        f"Candidate's answer (transcribed):\n{answer}"
    )


def score_answer(
    question: str,
    answer: str,
    competencies: List[Dict[str, Any]],
    role_title: str = "",
    only_relevant: bool = False,
    api_key: Optional[str] = None,
    client=None,
) -> Dict[str, Any]:
    """Score one answer; returns a schema-complete result dict (never raises on bad JSON).

    ``only_relevant`` (used in freeform mode, where the question isn't pre-mapped
    to competencies) tells the model to score only the competencies the answer
    actually addresses and omit the rest — so an answer isn't penalized on
    competencies its question was never about.
    """
    client = client or get_client(api_key)
    user = _build_user_prompt(question, answer, competencies, role_title)
    if only_relevant:
        user += (
            "\n\nIMPORTANT: This question was not pre-mapped to specific competencies. "
            "Include a competency in per_competency ONLY if the answer gives clear, "
            "relevant evidence for it; OMIT competencies the answer does not genuinely "
            "address (do not score them at all)."
        )
    data = chat_json(client, _SYSTEM, user, temperature=0.2)

    # Schema-complete so downstream report code can rely on the shape.
    result: Dict[str, Any] = {
        "score": _clamp_score(data.get("score")),
        "per_competency": {},
        "evidence_quotes": [],
        "strengths": [],
        "gaps": [],
        "rationale": str(data.get("rationale", "")),
    }
    valid_ids = {c["id"] for c in competencies}
    pc = data.get("per_competency") or {}
    if isinstance(pc, dict):
        for cid, val in pc.items():
            if not valid_ids or cid in valid_ids:
                result["per_competency"][cid] = _clamp_score(val)
    for key in _LIST_KEYS:
        vals = data.get(key) or []
        if isinstance(vals, list):
            result[key] = [str(v) for v in vals]
    return result


def _clamp_score(value: Any) -> Optional[int]:
    """Coerce a model score into an int in [1, 10]; ``None`` if unusable."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return max(1, min(10, n))
