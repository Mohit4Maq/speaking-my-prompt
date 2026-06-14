"""Output and sharing: save a bundle, copy to clipboard, build a Gmail draft.

The Gmail draft is **built here as a plain spec** (recipients/subject/body) and
returned to the caller; this module never sends mail and never calls the Gmail
integration itself. The CLI layer is responsible for handing the spec to the
Gmail draft tool after an explicit confirmation. This keeps `share.py` pure and
trivially testable (no network, no MCP).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from mom_pipeline.utils import ensure_dir, now_ts, safe_json_dump

from .meeting import Meeting
from .mom import render_html, render_markdown


@dataclass
class Bundle:
    """Paths written for one meeting, plus the rendered artifacts."""

    directory: str
    markdown: str
    html: str


def save_bundle(
    mom: Dict,
    meeting: Meeting,
    transcript_text: str,
    output_dir: str,
    prepared_by: str = "",
) -> Bundle:
    """Write transcript, mom.json, mom.md, mom.html, meeting.json under a folder."""
    out_dir = f"{output_dir.rstrip('/')}/{now_ts()}_{meeting.slug()}"
    ensure_dir(out_dir)

    md = render_markdown(mom, prepared_by=prepared_by)
    html = render_html(mom, prepared_by=prepared_by)

    with open(f"{out_dir}/transcript.txt", "w", encoding="utf-8") as f:
        f.write(transcript_text + "\n")
    safe_json_dump(mom, f"{out_dir}/mom.json")
    with open(f"{out_dir}/mom.md", "w", encoding="utf-8") as f:
        f.write(md)
    with open(f"{out_dir}/mom.html", "w", encoding="utf-8") as f:
        f.write(html)
    safe_json_dump(
        {
            "title": meeting.title,
            "datetime": meeting.datetime_iso,
            "participants": [p.__dict__ for p in meeting.participants],
            "agenda": meeting.agenda,
        },
        f"{out_dir}/meeting.json",
    )
    return Bundle(directory=out_dir, markdown=md, html=html)


def copy_to_clipboard(text: str) -> bool:
    """Copy ``text`` to the clipboard; return True on success (best-effort)."""
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception:  # noqa: BLE001 — clipboard is optional (headless/CI)
        return False


@dataclass
class EmailDraft:
    """A ready-to-create Gmail draft (the CLI hands this to the Gmail tool)."""

    to: List[str]
    subject: str
    html_body: str
    text_body: str


def build_email_draft(
    mom: Dict,
    meeting: Meeting,
    bundle: Bundle,
    extra_recipients: Optional[List[str]] = None,
) -> EmailDraft:
    """Assemble the email-draft spec for the MoM. Does not send anything."""
    recipients = list(meeting.recipient_emails())
    for r in extra_recipients or []:
        if r and r not in recipients:
            recipients.append(r)

    date_part = (meeting.datetime_iso or "").split("T")[0]
    title = mom.get("meetingTitle") or meeting.title or "Meeting"
    subject = f"Minutes of Meeting — {title}" + (f" ({date_part})" if date_part else "")

    return EmailDraft(
        to=recipients,
        subject=subject,
        html_body=bundle.html,
        text_body=bundle.markdown,
    )


def write_email_draft(draft: EmailDraft, directory: str) -> str:
    """Persist the draft spec to ``email_draft.json`` in the bundle; return its path.

    A separate Gmail integration (the agent's MCP tool, or a future OAuth client)
    reads this to create the actual draft. meet-mom itself never sends mail.
    """
    path = f"{directory.rstrip('/')}/email_draft.json"
    safe_json_dump(
        {"to": draft.to, "subject": draft.subject, "html_body": draft.html_body, "text_body": draft.text_body},
        path,
    )
    return path
