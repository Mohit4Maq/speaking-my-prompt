"""Meeting metadata: title, date/time, participants, agenda.

Loaded from CLI flags or an optional ``meeting.yaml``. Kept tiny and pure so the
session/MoM layers depend only on a plain dataclass, not on argparse or YAML.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Participant:
    """One attendee. ``email`` is optional and only used for the Gmail draft."""

    name: str
    role: str = ""
    email: Optional[str] = None

    @property
    def display(self) -> str:
        return f"{self.name} ({self.role})" if self.role else self.name


@dataclass
class Meeting:
    """All non-transcript context for a meeting."""

    title: str = ""
    datetime_iso: str = ""
    participants: List[Participant] = field(default_factory=list)
    agenda: List[str] = field(default_factory=list)
    host_name: str = "Host"

    def __post_init__(self) -> None:
        if not self.datetime_iso:
            self.datetime_iso = datetime.now().astimezone().isoformat(timespec="seconds")

    # -- views used by downstream layers ------------------------------------ #
    def participant_displays(self) -> List[str]:
        return [p.display for p in self.participants]

    def recipient_emails(self) -> List[str]:
        return [p.email for p in self.participants if p.email]

    def slug(self) -> str:
        base = (self.title or "meeting").lower()
        keep = [c if c.isalnum() else "-" for c in base]
        slug = "".join(keep).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug or "meeting"


# --------------------------------------------------------------------------- #
# Construction from flags / file
# --------------------------------------------------------------------------- #
def parse_participants(spec: str) -> List[Participant]:
    """Parse a ``--participants`` string into :class:`Participant` objects.

    Format: semicolon-separated entries, each ``Name (Role) <email>`` where
    ``(Role)`` and ``<email>`` are optional. Examples::

        "You (Host); Jane Doe (Acme, VP Product) <jane@acme.com>; Bob Lee"
    """
    out: List[Participant] = []
    for raw in spec.split(";"):
        entry = raw.strip()
        if not entry:
            continue
        email = None
        if "<" in entry and ">" in entry:
            start, end = entry.index("<"), entry.index(">")
            email = entry[start + 1 : end].strip() or None
            entry = (entry[:start] + entry[end + 1 :]).strip()
        role = ""
        if "(" in entry and entry.endswith(")"):
            open_paren = entry.index("(")
            role = entry[open_paren + 1 : -1].strip()
            entry = entry[:open_paren].strip()
        name = entry.strip()
        if name:
            out.append(Participant(name=name, role=role, email=email))
    return out


def load_agenda(path: Optional[str]) -> List[str]:
    """Read an agenda file: one item per non-empty line (leading bullets stripped)."""
    if not path:
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    items = []
    for line in lines:
        item = line.strip().lstrip("-*•").strip()
        if item:
            items.append(item)
    return items


def build_meeting(
    title: str = "",
    datetime_iso: str = "",
    participants_spec: str = "",
    agenda_path: Optional[str] = None,
    host_name: str = "Host",
) -> Meeting:
    """Assemble a :class:`Meeting` from CLI-style inputs."""
    return Meeting(
        title=title,
        datetime_iso=datetime_iso,
        participants=parse_participants(participants_spec) if participants_spec else [],
        agenda=load_agenda(agenda_path),
        host_name=host_name or "Host",
    )
