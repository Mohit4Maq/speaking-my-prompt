"""Rich live panel for an in-progress meeting capture: a rolling transcript.

Decoupled from the capture thread so transcription latency never freezes the
display. Mirrors the pattern in ``interview_eval.display``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:  # avoid import cycle at runtime
    from .session import MeetingSession

_MAX_LINES = 20


def render(session: "MeetingSession") -> Panel:
    """Build the live transcript renderable from current session state."""
    from .session import _fmt_ts, HOST

    body = Text()
    rows = session.transcript[-_MAX_LINES:]
    for ts, speaker, line in rows:
        stamp = f"[{_fmt_ts(ts)}] "
        if speaker == HOST:
            body.append(stamp, style="dim")
            body.append("Host:   ", style="bold cyan")
            body.append(line + "\n", style="cyan")
        else:
            body.append(stamp, style="dim")
            body.append("Client: ", style="bold green")
            body.append(line + "\n", style="green")
    if not rows:
        body = Text("(listening… speak naturally)", style="dim italic")

    title = session.meeting.title or "Meeting"
    return Panel(
        body,
        title=f"meet-mom · {title} · live transcript",
        subtitle="Ctrl+C to end and generate the minutes",
        border_style="blue",
    )
