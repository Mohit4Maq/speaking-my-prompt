from typing import Dict, List, Tuple

from openai import OpenAI

from .config import MOM_MODEL


MOM_SCHEMA_KEYS = {
    "meetingTitle",
    "dateTime",
    "platform",
    "participants",
    "agenda",
    "discussion",
    "decisions",
    "actionItems",
    "risks",
    "dependencies",
    "openQuestions",
    "summary",
}


def _build_system_prompt() -> str:
    return (
        "You are a meticulous meeting minutes generator. "
        "Use ONLY facts present in the transcript. "
        "Do NOT invent speakers, owners, dates, or facts. "
        "If data is missing, use empty lists/strings or nulls. "
        "Return JSON with strictly the specified keys and types."
    )


def _build_user_prompt(transcript_text: str, metadata: Dict) -> str:
    base = {
        "meetingTitle": metadata.get("title") or "",
        "dateTime": metadata.get("datetime") or "",
        "platform": "Google Meet",
        "participants": metadata.get("participants") or [],
    }

    guidance = (
        "Target structure: {\n"
        "  meetingTitle: string,\n"
        "  dateTime: string (ISO if available),\n"
        "  platform: 'Google Meet',\n"
        "  participants: string[],\n"
        "  agenda: string[],\n"
        "  discussion: [{topic: string, points: string[]}],\n"
        "  decisions: string[],\n"
        "  actionItems: [{task: string, owner: string|null, dueDate: string|null, priority: string|null}],\n"
        "  risks: string[],\n"
        "  dependencies: string[],\n"
        "  openQuestions: string[],\n"
        "  summary: string[5..8]\n"
        "}.\n"
        "Fill only from transcript; otherwise leave empty or null."
    )
    return (
        f"Metadata: {base}\n\n"
        f"Transcript (cleaned):\n{transcript_text}\n\n"
        f"{guidance}"
    )


def generate_mom(transcript_text: str, metadata: Dict) -> Dict:
    client = OpenAI()
    sys_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(transcript_text, metadata)

    resp = client.chat.completions.create(
        model=MOM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = resp.choices[0].message.content
    mom = {}  # will parse to dict
    try:
        import json

        mom = json.loads(content)
    except Exception:
        mom = {}

    # Ensure key completeness and types
    for k in MOM_SCHEMA_KEYS:
        if k not in mom:
            mom[k] = [] if k in {
                "participants",
                "agenda",
                "discussion",
                "decisions",
                "actionItems",
                "risks",
                "dependencies",
                "openQuestions",
                "summary",
            } else ""
    mom["platform"] = "Google Meet"
    return mom


def render_markdown(mom: Dict) -> str:
    # Deterministic Markdown rendering
    parts: List[str] = []
    parts.append(f"# Minutes of Meeting: {mom.get('meetingTitle','').strip()}")
    parts.append("")
    parts.append(f"- Date & Time: {mom.get('dateTime','').strip()}")
    parts.append(f"- Platform: Google Meet")
    participants = mom.get("participants", [])
    parts.append(f"- Participants: {', '.join(participants) if participants else '—'}")
    parts.append("")
    agenda = mom.get("agenda", [])
    parts.append("## Agenda")
    if agenda:
        for a in agenda:
            parts.append(f"- {a}")
    else:
        parts.append("- —")
    parts.append("")

    parts.append("## Key Discussion Points")
    discussion = mom.get("discussion", [])
    if discussion:
        for d in discussion:
            parts.append(f"- {d.get('topic','')}")
            for p in d.get("points", []):
                parts.append(f"  - {p}")
    else:
        parts.append("- —")
    parts.append("")

    parts.append("## Decisions Taken")
    decisions = mom.get("decisions", [])
    if decisions:
        for d in decisions:
            parts.append(f"- {d}")
    else:
        parts.append("- —")
    parts.append("")

    parts.append("## Action Items")
    items = mom.get("actionItems", [])
    if items:
        for it in items:
            owner = it.get("owner") or "—"
            due = it.get("dueDate") or "—"
            prio = it.get("priority") or "—"
            parts.append(f"- Task: {it.get('task','')} | Owner: {owner} | Due: {due} | Priority: {prio}")
    else:
        parts.append("- —")
    parts.append("")

    parts.append("## Risks / Dependencies")
    risks = mom.get("risks", [])
    deps = mom.get("dependencies", [])
    parts.append("- Risks:")
    if risks:
        for r in risks:
            parts.append(f"  - {r}")
    else:
        parts.append("  - —")
    parts.append("- Dependencies:")
    if deps:
        for d in deps:
            parts.append(f"  - {d}")
    else:
        parts.append("  - —")
    parts.append("")

    parts.append("## Open Questions")
    oq = mom.get("openQuestions", [])
    if oq:
        for q in oq:
            parts.append(f"- {q}")
    else:
        parts.append("- —")
    parts.append("")

    parts.append("## Summary Overview")
    summary = mom.get("summary", [])
    if summary:
        for s in summary:
            parts.append(f"- {s}")
    else:
        parts.append("- —")

    return "\n".join(parts)
