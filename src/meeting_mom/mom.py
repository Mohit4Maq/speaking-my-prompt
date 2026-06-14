"""Minutes-of-Meeting generation and client-grade rendering.

Builds on ``mom_pipeline.mom_generate`` (schema + anti-hallucination prompt) but:
  * ingests a **speaker-labeled** transcript (Host / Client),
  * adds a ``nextSteps`` section for a client-facing document,
  * defaults to ``gpt-4o`` for stronger synthesis/attribution,
  * renders both polished **Markdown** and a clean **HTML** email body.

Rendering is deterministic (no extra LLM call) so the document is stable.
"""
from __future__ import annotations

import json
from html import escape
from typing import Dict, List

from openai import OpenAI
from mom_pipeline.llm import chat_json, get_client
from mom_pipeline.mom_generate import MoMGenerator, MOM_SCHEMA_KEYS

from .meeting import Meeting

DEFAULT_MOM_MODEL = "gpt-4o"

# Extends mom_pipeline's MOM_SCHEMA_KEYS with client-facing ``nextSteps``.
LIST_KEYS = {
    "participants", "agenda", "discussion", "decisions", "actionItems",
    "risks", "dependencies", "openQuestions", "nextSteps", "summary",
}
STRING_KEYS = {"meetingTitle", "dateTime", "platform"}
MOM_SCHEMA_KEYS = LIST_KEYS | STRING_KEYS


class ClientMoMGenerator(MoMGenerator):
    """Implementation for polished client-facing meeting minutes."""
    def build_system_prompt(self) -> str:
        return (
            "You are a meticulous executive assistant producing client-facing meeting "
            "minutes for a high-value account. Use ONLY facts present in the transcript. "
            "Do NOT invent speakers, owners, dates, decisions, or commitments. "
            "The transcript is speaker-labeled as 'Host' (our side) and 'Client' (the "
            "client side); attribute action-item owners accordingly, using a named "
            "participant only when the transcript makes the attribution clear, else the "
            "side ('Host'/'Client') or null. Keep wording professional and concise. "
            "\n\n"
            "INCLUDE ONLY substantive, work-related content: business/project topics, "
            "requirements, scope, timelines, budgets, decisions, commitments, risks, "
            "dependencies, and follow-ups. "
            "EXCLUDE entirely (do not record anywhere, not even in the summary): "
            "greetings and goodbyes, small talk and pleasantries, off-topic chatter "
            "(world news, politics, weather, sports, family/personal life, holidays), "
            "audio/connection issues ('can you hear me?'), and any banter unrelated to "
            "the work. If a turn is purely social or off-topic, ignore it. "
            "If data for a field is missing, use an empty list or empty string. "
            "Return JSON with strictly the specified keys and types."
        )

    def build_user_prompt(self, transcript_text: str, meeting: Meeting) -> str:
        base = {
            "meetingTitle": meeting.title or "",
            "dateTime": meeting.datetime_iso or "",
            "platform": "Google Meet",
            "participants": meeting.participant_displays(),
            "knownAgenda": meeting.agenda,
        }
        guidance = (
            "Target JSON structure: {\n"
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
            "  nextSteps: string[],\n"
            "  summary: string[5..8]\n"
            "}.\n"
            "If knownAgenda is provided, use it to seed 'agenda' but refine from the "
            "actual discussion. Fill every field only from the transcript; otherwise "
            "leave it empty."
        )
        return (
            f"Meeting metadata: {json.dumps(base)}\n\n"
            f"Speaker-labeled transcript:\n{transcript_text}\n\n"
            f"{guidance}"
        )

    def normalize(self, mom: Dict, meeting: Meeting) -> Dict:
        """Guarantee key completeness/types and stamp known metadata."""
        for k in LIST_KEYS:
            if not isinstance(mom.get(k), list):
                mom[k] = []
        for k in STRING_KEYS:
            if not isinstance(mom.get(k), str):
                mom[k] = ""
        mom["platform"] = "Google Meet"
        if not mom.get("meetingTitle"):
            mom["meetingTitle"] = meeting.title
        if not mom.get("dateTime"):
            mom["dateTime"] = meeting.datetime_iso
        if not mom.get("participants"):
            mom["participants"] = meeting.participant_displays()
        return mom


def generate_mom(
    transcript_text: str,
    meeting: Meeting,
    model: str = DEFAULT_MOM_MODEL,
    client: OpenAI | None = None,
) -> Dict:
    """Generate the MoM dict from a speaker-labeled transcript."""
    generator = ClientMoMGenerator(model=model)
    return generator.generate(transcript_text, meeting, client=client)


# --------------------------------------------------------------------------- #
# Functional shims — keep the pre-refactor module-level API stable for callers
# and tests. These delegate to a single shared ClientMoMGenerator so there is
# still one source of truth for the prompt/normalization logic.
# --------------------------------------------------------------------------- #
_DEFAULT_GENERATOR = ClientMoMGenerator()


def _system_prompt() -> str:
    """Return the client-facing MoM system prompt (delegates to the generator)."""
    return _DEFAULT_GENERATOR.build_system_prompt()


def _normalize(mom: Dict, meeting: Meeting) -> Dict:
    """Guarantee key completeness/types and stamp known metadata."""
    return _DEFAULT_GENERATOR.normalize(mom, meeting)


# --------------------------------------------------------------------------- #
# Rendering — deterministic Markdown
# --------------------------------------------------------------------------- #
def render_markdown(mom: Dict, prepared_by: str = "") -> str:
    """Render the MoM dict as polished, client-facing Markdown."""
    p: List[str] = []
    p.append(f"# Minutes of Meeting — {mom.get('meetingTitle', '').strip() or 'Untitled'}")
    p.append("")
    p.append(f"**Date & Time:** {mom.get('dateTime', '').strip() or '—'}  ")
    p.append("**Platform:** Google Meet  ")
    participants = mom.get("participants", [])
    p.append(f"**Attendees:** {', '.join(participants) if participants else '—'}  ")
    if prepared_by:
        p.append(f"**Prepared by:** {prepared_by}  ")
    p.append("")

    summary = mom.get("summary", [])
    if summary:
        p.append("## Executive Summary")
        for s in summary:
            p.append(f"- {s}")
        p.append("")

    p.append("## Agenda")
    _bullets(p, mom.get("agenda", []))
    p.append("")

    p.append("## Discussion")
    discussion = mom.get("discussion", [])
    if discussion:
        for d in discussion:
            p.append(f"### {d.get('topic', '').strip() or 'Topic'}")
            for pt in d.get("points", []):
                p.append(f"- {pt}")
    else:
        p.append("- —")
    p.append("")

    p.append("## Decisions")
    _bullets(p, mom.get("decisions", []))
    p.append("")

    p.append("## Action Items")
    items = mom.get("actionItems", [])
    if items:
        p.append("| # | Task | Owner | Due | Priority |")
        p.append("|---|---|---|---|---|")
        for i, it in enumerate(items, start=1):
            p.append(
                f"| {i} | {it.get('task', '')} | {it.get('owner') or '—'} "
                f"| {it.get('dueDate') or '—'} | {it.get('priority') or '—'} |"
            )
    else:
        p.append("_None recorded._")
    p.append("")

    p.append("## Next Steps")
    _bullets(p, mom.get("nextSteps", []))
    p.append("")

    risks, deps = mom.get("risks", []), mom.get("dependencies", [])
    if risks or deps:
        p.append("## Risks & Dependencies")
        if risks:
            p.append("**Risks:**")
            _bullets(p, risks)
        if deps:
            p.append("**Dependencies:**")
            _bullets(p, deps)
        p.append("")

    oq = mom.get("openQuestions", [])
    if oq:
        p.append("## Open Questions")
        _bullets(p, oq)
        p.append("")

    p.append("---")
    p.append("_Auto-generated from the meeting transcript; please review for accuracy._")
    return "\n".join(p).rstrip() + "\n"


def _bullets(p: List[str], items: List[str]) -> None:
    if items:
        for it in items:
            p.append(f"- {it}")
    else:
        p.append("- —")


# --------------------------------------------------------------------------- #
# Rendering — clean HTML email body
# --------------------------------------------------------------------------- #
def render_html(mom: Dict, prepared_by: str = "") -> str:
    """Render a self-contained, inline-styled HTML body for an email."""
    e = escape
    h: List[str] = []
    h.append(
        '<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;'
        'color:#1a1a1a;line-height:1.5;max-width:720px">'
    )
    h.append(f'<h1 style="margin:0 0 8px">Minutes of Meeting — {e(mom.get("meetingTitle", "") or "Untitled")}</h1>')
    h.append('<div style="color:#555;font-size:14px;margin-bottom:16px">')
    h.append(f'<div><b>Date &amp; Time:</b> {e(mom.get("dateTime", "") or "—")}</div>')
    h.append("<div><b>Platform:</b> Google Meet</div>")
    parts = mom.get("participants", [])
    h.append(f'<div><b>Attendees:</b> {e(", ".join(parts)) if parts else "—"}</div>')
    if prepared_by:
        h.append(f"<div><b>Prepared by:</b> {e(prepared_by)}</div>")
    h.append("</div>")

    def section(title: str) -> None:
        h.append(f'<h2 style="margin:20px 0 6px;font-size:18px;border-bottom:1px solid #eee;padding-bottom:4px">{e(title)}</h2>')

    def ul(items: List[str]) -> None:
        if not items:
            h.append('<p style="color:#999;margin:4px 0">—</p>')
            return
        h.append('<ul style="margin:6px 0 6px 20px;padding:0">')
        for it in items:
            h.append(f"<li>{e(str(it))}</li>")
        h.append("</ul>")

    if mom.get("summary"):
        section("Executive Summary")
        ul(mom["summary"])

    section("Agenda")
    ul(mom.get("agenda", []))

    section("Discussion")
    discussion = mom.get("discussion", [])
    if discussion:
        for d in discussion:
            h.append(f'<h3 style="margin:12px 0 4px;font-size:15px">{e(d.get("topic", "") or "Topic")}</h3>')
            ul(d.get("points", []))
    else:
        ul([])

    section("Decisions")
    ul(mom.get("decisions", []))

    section("Action Items")
    items = mom.get("actionItems", [])
    if items:
        h.append('<table style="border-collapse:collapse;width:100%;font-size:14px">')
        h.append(
            '<tr style="background:#f5f5f5">'
            '<th style="text-align:left;padding:6px;border:1px solid #e5e5e5">Task</th>'
            '<th style="text-align:left;padding:6px;border:1px solid #e5e5e5">Owner</th>'
            '<th style="text-align:left;padding:6px;border:1px solid #e5e5e5">Due</th>'
            '<th style="text-align:left;padding:6px;border:1px solid #e5e5e5">Priority</th></tr>'
        )
        for it in items:
            h.append(
                "<tr>"
                f'<td style="padding:6px;border:1px solid #e5e5e5">{e(it.get("task", ""))}</td>'
                f'<td style="padding:6px;border:1px solid #e5e5e5">{e(it.get("owner") or "—")}</td>'
                f'<td style="padding:6px;border:1px solid #e5e5e5">{e(it.get("dueDate") or "—")}</td>'
                f'<td style="padding:6px;border:1px solid #e5e5e5">{e(it.get("priority") or "—")}</td></tr>'
            )
        h.append("</table>")
    else:
        h.append('<p style="color:#999;margin:4px 0">None recorded.</p>')

    section("Next Steps")
    ul(mom.get("nextSteps", []))

    if mom.get("risks") or mom.get("dependencies"):
        section("Risks & Dependencies")
        if mom.get("risks"):
            h.append("<p style=\"margin:6px 0 0\"><b>Risks</b></p>")
            ul(mom["risks"])
        if mom.get("dependencies"):
            h.append("<p style=\"margin:6px 0 0\"><b>Dependencies</b></p>")
            ul(mom["dependencies"])

    if mom.get("openQuestions"):
        section("Open Questions")
        ul(mom["openQuestions"])

    h.append(
        '<p style="color:#999;font-size:12px;margin-top:20px;border-top:1px solid #eee;'
        'padding-top:8px">Auto-generated from the meeting transcript; please review for accuracy.</p>'
    )
    h.append("</div>")
    return "\n".join(h)
