"""Load the interview question bank and match interviewer speech to questions.

Questions are authored in ``questions.yaml`` and mapped to competency ids. At
startup every question is embedded once (``text-embedding-3-small``). When the
interviewer speaks, the utterance is embedded and cosine-matched to the nearest
question; matches below a threshold leave the active question unchanged (the
interviewer was commenting, not asking a new question).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

import numpy as np
import yaml

from mom_pipeline.llm import get_client, embed

# Tokens ignored when comparing competency labels to JD competency names.
_STOPWORDS = {"and", "or", "of", "the", "a", "an", "to", "for", "with", "in", "on"}


def _tokens(text: str) -> Set[str]:
    """Lowercase alphanumeric tokens minus stopwords (for overlap matching)."""
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if t and t not in _STOPWORDS}


@dataclass
class Question:
    id: str
    question: str
    competencies: List[str] = field(default_factory=list)
    notes: str = ""


def load_questions(path: str) -> List[Question]:
    """Load and validate ``questions.yaml`` into ``Question`` objects."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []
    if not isinstance(raw, list):
        raise ValueError("questions.yaml must be a YAML list of question entries")

    questions: List[Question] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not item.get("question"):
            raise ValueError(f"Question entry #{i + 1} must have a 'question' field")
        questions.append(
            Question(
                id=str(item.get("id") or f"q{i + 1}"),
                question=str(item["question"]),
                competencies=[str(c) for c in (item.get("competencies") or [])],
                notes=str(item.get("notes", "")),
            )
        )
    return questions


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(np.dot(a, b) / denom)


def align_question_competencies(
    questions: List[Question],
    jd_competencies: List[dict],
    api_key: Optional[str] = None,
    client=None,
    threshold: float = 0.30,
) -> dict:
    """Remap hand-authored question competency labels to real JD competency ids.

    The ids written in ``questions.yaml`` (e.g. ``api-design``) rarely match the
    slugs the JD parser generates (e.g. ``python-and-api-design``). This embeds
    each JD competency (name + description) and each unique question label, then
    rewrites every question's competencies to the nearest JD id. Labels that
    already equal a JD id pass through; labels below ``threshold`` are dropped
    (the scorer then falls back to the full rubric for that question).

    Mutates ``questions`` in place. Returns ``{original_label: jd_id|None}``.
    """
    if not jd_competencies:
        return {}

    jd_ids = [c["id"] for c in jd_competencies]
    jd_id_set = set(jd_ids)
    labels = sorted({lab for q in questions for lab in q.competencies})
    if not labels:
        return {}

    # Reference text per JD competency = name (or id), tokenized. Matched against
    # short question labels using token overlap first — robust where embeddings
    # are not (e.g. "api-design" shares two tokens with "Python and API Design"
    # but only one with "System Design", so overlap picks the right one even
    # though embedding similarity is dominated by the shared word "design").
    jd_names = [(c.get("name") or c["id"]) for c in jd_competencies]
    jd_token_sets = [_tokens(n) for n in jd_names]

    mapping: dict = {lab: lab for lab in labels if lab in jd_id_set}
    unresolved = [lab for lab in labels if lab not in mapping]

    # Pass 1: unambiguous token overlap.
    embed_needed = []
    for lab in unresolved:
        lab_tokens = _tokens(lab)
        overlaps = [len(lab_tokens & ts) for ts in jd_token_sets]
        best_ov = max(overlaps) if overlaps else 0
        if best_ov > 0 and overlaps.count(best_ov) == 1:
            mapping[lab] = jd_ids[overlaps.index(best_ov)]
        else:
            embed_needed.append(lab)  # zero overlap or a tie → fall back to embeddings

    # Pass 2: embedding similarity for anything token overlap couldn't resolve.
    if embed_needed:
        client = client or get_client(api_key)
        jd_vecs = np.array(embed(client, [n.replace("-", " ").replace("_", " ") for n in jd_names]), dtype=np.float32)
        lab_vecs = np.array(embed(client, [lab.replace("-", " ").replace("_", " ") for lab in embed_needed]), dtype=np.float32)
        for lab, vec in zip(embed_needed, lab_vecs):
            sims = [_cosine(vec, jd_vecs[i]) for i in range(len(jd_ids))]
            best = int(np.argmax(sims))
            mapping[lab] = jd_ids[best] if sims[best] >= threshold else None

    for q in questions:
        remapped: List[str] = []
        for lab in q.competencies:
            target = mapping.get(lab, lab)
            if target and target not in remapped:
                remapped.append(target)
        q.competencies = remapped

    return mapping


class QuestionBank:
    """Embeds the question set and matches interviewer utterances to questions."""

    def __init__(
        self,
        questions: List[Question],
        api_key: Optional[str] = None,
        match_threshold: float = 0.35,
    ) -> None:
        self.questions = questions
        self.match_threshold = match_threshold
        self._client = get_client(api_key)
        texts = [q.question for q in questions]
        self._embeddings = (
            np.array(embed(self._client, texts), dtype=np.float32)
            if texts
            else np.zeros((0, 1), dtype=np.float32)
        )

    def match(self, utterance: str) -> Tuple[Optional[Question], float]:
        """Return the best-matching question and its similarity for an utterance.

        Returns ``(None, score)`` when the best similarity is below the
        threshold, signalling the caller to keep the current active question.
        """
        if not utterance.strip() or len(self.questions) == 0:
            return None, 0.0
        vec = np.array(embed(self._client, [utterance])[0], dtype=np.float32)
        sims = [_cosine(vec, self._embeddings[i]) for i in range(len(self.questions))]
        best = int(np.argmax(sims))
        score = sims[best]
        if score < self.match_threshold:
            return None, score
        return self.questions[best], score

    def get(self, question_id: str) -> Optional[Question]:
        return next((q for q in self.questions if q.id == question_id), None)
