"""Aggregate per-answer scores into a weighted competency report.

Per competency: average of all answer-level scores tagged with it. Weighted
overall = sum(weight * competency_average) over competencies that received at
least one score (weights renormalized over those). A hire band is derived from
the overall. Renders a Markdown report (deterministic, like
``mom_generate.render_markdown``) plus a JSON dump.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mom_pipeline.utils import ensure_dir, now_ts, safe_json_dump

# Hire bands: (inclusive lower bound, label), checked high-to-low.
HIRE_BANDS = [
    (8.0, "Strong hire"),
    (6.5, "Lean hire"),
    (5.0, "Borderline"),
    (0.0, "No hire"),
]


def hire_band(overall: Optional[float]) -> str:
    if overall is None:
        return "Insufficient data"
    for lower, label in HIRE_BANDS:
        if overall >= lower:
            return label
    return "No hire"


def aggregate(
    competencies: List[Dict[str, Any]],
    answers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute per-competency averages and a weighted overall score.

    Args:
        competencies: ``[{id, name, weight, ...}]`` from the JD parse.
        answers: one entry per scored answer, each containing at least
            ``per_competency: {comp_id: score}`` (and usually ``score``,
            ``question_id``, ``question``, ``answer``, ``evidence_quotes``, ...).

    Returns a dict with ``per_competency`` (id -> {name, weight, average, n}),
    ``overall`` (weighted, 1-10 or None), and ``band``.
    """
    weight_by_id = {c["id"]: float(c.get("weight", 0.0)) for c in competencies}
    name_by_id = {c["id"]: c.get("name", c["id"]) for c in competencies}

    # Collect scores per competency across all answers.
    scores: Dict[str, List[int]] = {c["id"]: [] for c in competencies}
    for ans in answers:
        for cid, val in (ans.get("per_competency") or {}).items():
            if val is None:
                continue
            scores.setdefault(cid, []).append(int(val))

    per_competency: Dict[str, Dict[str, Any]] = {}
    weighted_sum = 0.0
    weight_total = 0.0
    for cid, vals in scores.items():
        avg = (sum(vals) / len(vals)) if vals else None
        per_competency[cid] = {
            "name": name_by_id.get(cid, cid),
            "weight": weight_by_id.get(cid, 0.0),
            "average": avg,
            "n": len(vals),
        }
        if avg is not None:
            w = weight_by_id.get(cid, 0.0)
            weighted_sum += w * avg
            weight_total += w

    overall = (weighted_sum / weight_total) if weight_total > 0 else None
    return {
        "per_competency": per_competency,
        "overall": round(overall, 2) if overall is not None else None,
        "band": hire_band(overall),
    }


def build_report(
    role_title: str,
    competencies: List[Dict[str, Any]],
    answers: List[Dict[str, Any]],
    candidate_name: str = "",
) -> Dict[str, Any]:
    """Assemble the full report object (JSON-serializable)."""
    summary = aggregate(competencies, answers)
    return {
        "candidate": candidate_name,
        "role_title": role_title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": summary["overall"],
        "band": summary["band"],
        "competencies": summary["per_competency"],
        "answers": answers,
    }


def _fmt(x: Optional[float]) -> str:
    return f"{x:.1f}" if isinstance(x, (int, float)) else "—"


def render_markdown(report: Dict[str, Any]) -> str:
    """Deterministically render the report dict as Markdown."""
    p: List[str] = []
    title = report.get("role_title") or "Interview"
    p.append(f"# Interview Evaluation: {title}")
    if report.get("candidate"):
        p.append(f"**Candidate:** {report['candidate']}")
    p.append(f"**Generated:** {report.get('generated_at', '')}")
    p.append("")
    p.append(f"## Overall: {_fmt(report.get('overall'))} / 10 — {report.get('band', '')}")
    p.append("")

    p.append("## Competency Scores")
    p.append("")
    p.append("| Competency | Weight | Avg | Answers |")
    p.append("|---|---|---|---|")
    for cid, c in report.get("competencies", {}).items():
        weight_pct = f"{c.get('weight', 0.0) * 100:.0f}%"
        p.append(
            f"| {c.get('name', cid)} | {weight_pct} | {_fmt(c.get('average'))} | {c.get('n', 0)} |"
        )
    p.append("")

    p.append("## Per-Question Detail")
    p.append("")
    for i, ans in enumerate(report.get("answers", []), start=1):
        p.append(f"### Q{i}. {ans.get('question', '(unmatched question)')}")
        p.append(f"- **Score:** {_fmt(ans.get('score'))}/10")
        if ans.get("rationale"):
            p.append(f"- **Rationale:** {ans['rationale']}")
        quotes = ans.get("evidence_quotes") or []
        if quotes:
            p.append("- **Evidence:**")
            for q in quotes:
                p.append(f'  - "{q}"')
        strengths = ans.get("strengths") or []
        if strengths:
            p.append("- **Strengths:** " + "; ".join(strengths))
        gaps = ans.get("gaps") or []
        if gaps:
            p.append("- **Gaps:** " + "; ".join(gaps))
        if ans.get("answer"):
            p.append(f"- **Answer (transcript):** {ans['answer']}")
        p.append("")

    p.append("---")
    p.append(
        "_Scores are AI-generated decision support, not a hiring verdict. "
        "Review evidence quotes and apply your own judgment._"
    )
    return "\n".join(p)


def save_report(report: Dict[str, Any], output_dir: str) -> str:
    """Write ``report.md`` and ``report.json`` under a timestamped folder; return the folder."""
    out_dir = f"{output_dir.rstrip('/')}/{now_ts()}_interview"
    ensure_dir(out_dir)
    safe_json_dump(report, f"{out_dir}/report.json")
    with open(f"{out_dir}/report.md", "w", encoding="utf-8") as f:
        f.write(render_markdown(report))
    return out_dir
