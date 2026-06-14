"""Rich live TUI rendering for an in-progress interview session.

Reads shared :class:`~interview_eval.session.InterviewSession` state and renders
the active question, a rolling color-coded transcript, and a running competency
scoreboard. Rendering is decoupled from the session thread, so transcription /
scoring latency never freezes the display.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:  # avoid import cycle at runtime
    from .session import InterviewSession

_MAX_TRANSCRIPT_LINES = 16


def render(session: "InterviewSession") -> Panel:
    """Build the live dashboard renderable from current session state."""
    # Active question header.
    if session.active_question is not None:
        header = Text(f"▶ {session.active_question.question}", style="bold yellow")
    else:
        header = Text("Waiting for first question…", style="dim italic")

    # Rolling transcript (color-coded by speaker).
    transcript = Text()
    for speaker, line in session.transcript[-_MAX_TRANSCRIPT_LINES:]:
        if speaker == "interviewer":
            transcript.append("You:  ", style="bold cyan")
            transcript.append(line + "\n", style="cyan")
        else:
            transcript.append("Cand: ", style="bold green")
            transcript.append(line + "\n", style="green")
    if not session.transcript:
        transcript = Text("(no speech yet)", style="dim")

    # Live scoreboard from answers gathered so far.
    table = Table(expand=True, show_edge=False)
    table.add_column("Competency", style="white")
    table.add_column("Weight", justify="right")
    table.add_column("Avg", justify="right")
    table.add_column("n", justify="right")
    snap = session.snapshot_scores()
    for cid, c in snap["per_competency"].items():
        avg = c["average"]
        avg_txt = f"{avg:.1f}" if avg is not None else "—"
        style = _score_style(avg)
        table.add_row(
            c["name"], f"{c['weight'] * 100:.0f}%", Text(avg_txt, style=style), str(c["n"])
        )
    overall = snap["overall"]
    overall_txt = (
        f"Overall: {overall:.1f}/10 — {snap['band']}" if overall is not None else "Overall: —"
    )

    body = Group(
        Panel(header, border_style="yellow"),
        Panel(transcript, title="Transcript", border_style="blue"),
        Panel(table, title=overall_txt, border_style="magenta"),
        Text("Speak naturally · Ctrl+C to end and generate the report", style="dim"),
    )
    return Panel(body, title="hire-eval · live interview", border_style="bright_black")


def _score_style(avg) -> str:
    if avg is None:
        return "dim"
    if avg >= 7.5:
        return "bold green"
    if avg >= 5.5:
        return "yellow"
    return "red"
