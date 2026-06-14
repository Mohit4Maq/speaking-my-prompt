# Plan: Client-Meeting Minutes (MoM) from Google Meet

**Status:** Draft for review — no code written yet.
**Goal:** Capture both sides of a high-end client meeting over Google Meet using
the *same verified audio routing* we built for `hire-eval`, then auto-generate a
polished, properly formatted **Minutes of Meeting** and share it after the call.

---

## 1. What we already have (reuse, don't rebuild)

| Asset | Where | Reuse for MoM |
|---|---|---|
| Two-channel live capture (host=ch0, client=ch1) | `interview_eval/audio_router.py` (`UtteranceSegmenter`, `open_input_stream`, `utterance_to_wav`, device discovery) | **Verbatim** — same `hire-eval input Device`, same channel split |
| Offline stereo-WAV replay | `interview_eval/audio_router.py` (`SimulatedSource`), `session.run_simulated` pattern | Offline `simulate` mode for MoM |
| Whisper transcription | `mom_pipeline/live_transcribe.transcribe_audio` | Verbatim |
| MoM schema + JSON generation | `mom_pipeline/mom_generate.py` (`generate_mom`, `render_markdown`, `MOM_SCHEMA_KEYS`) | Extend (schema is already good: agenda/discussion/decisions/actionItems/risks/dependencies/openQuestions/summary) |
| Audio cleanup + WAV encode | `mom_pipeline/live_capture._preprocess_audio`, `_array_to_wav` | Verbatim (already used by audio_router) |
| API-key resolution, consent banner, report-saving pattern | `interview_eval/cli.py` | Mirror |

**Key insight:** the audio capture is identical to `hire-eval run` — only the
*back end* changes. Instead of "match question → score answer," we do "label
speaker → append to transcript → generate MoM at the end."

---

## 2. Architecture

### 2.1 New package + entrypoint
Create **`src/meeting_mom/`** with a new console script **`meet-mom`** (added to
`pyproject.toml [project.scripts]` alongside `hire-eval`). Keeping it a separate
tool (not a `hire-eval` subcommand) is cleaner: different purpose, different
output, no scoring/JD machinery.

### 2.2 Dependency direction (avoid a cycle)
- `interview_eval` already imports **from** `mom_pipeline`. So `mom_pipeline`
  must **not** import `interview_eval` (would be circular).
- The shared audio engine (`audio_router`) currently lives in `interview_eval`.

**Decision needed (see §8, Decision A).** Two clean options:
- **A1 — Pragmatic (recommended for v1):** `meeting_mom` imports
  `audio_router` from `interview_eval` and `generate_mom` from `mom_pipeline`.
  Zero changes to existing code → **zero risk to the 29 passing hire-eval tests.**
  Slight oddity: depending on `interview_eval` just for audio.
- **A2 — Clean long-term:** promote `audio_router` into a neutral
  `src/audio_core/` package; `interview_eval`, `meeting_mom` both import it.
  Better layering, but touches `interview_eval` imports (must re-run its tests).

Recommendation: **ship A1 now, file A2 as a follow-up refactor** so we don't risk
the working interview tool while adding a feature.

### 2.3 Module layout (`src/meeting_mom/`)
```
cli.py        # `meet-mom` entrypoint: subcommands record / simulate / from-transcript / list-devices / check-audio
session.py    # MeetingSession core (pure, testable): accepts host/client utterances, builds a timestamped speaker-labeled transcript; drivers run_live / run_simulated
mom.py        # MoM generation: wraps/extends mom_pipeline.generate_mom; adds speaker-aware prompt + polished client-facing renderers (Markdown, optional HTML)
share.py      # Output + sharing: clipboard, save to disk, optional Gmail draft to participants
meeting.py    # Meeting metadata model (title, datetime, participants/roster, agenda) loaded from flags or meeting.yaml
display.py    # Optional rich live transcript panel (reuse pattern from interview_eval/display.py)
```
`list-devices` and `check-audio` can be thin re-exports of the existing
`interview_eval.audio_router` helpers so users verify routing the same way.

---

## 3. Capture & transcript model

- **Channels:** ch0 = **Host** (you), ch1 = **Client side** (everyone on the Meet
  call, since they arrive as one mixed stream via BlackHole).
- **Honest limitation:** hardware channels separate *Host vs Client side*, **not
  individual client participants** — they're all in the Meet mix on ch1. We will
  **not** fake per-person diarization. Instead:
  - The user supplies a participant **roster** (names/roles) for the MoM header.
  - GPT may *best-effort* attribute action items to a named participant from
    context, but the transcript itself is labeled `Host` / `Client`.
  - (Future option noted in §7: optional ML diarization on ch1 via pyannote.)
- **`MeetingSession` (pure core, unit-testable):**
  - `on_host_utterance(wav_bytes)` / `on_client_utterance(wav_bytes)` → transcribe
    → append `(timestamp, speaker, text)` to an ordered transcript.
  - Timestamps derived from cumulative sample counts (deterministic; same trick
    `UtteranceSegmenter` already uses), formatted `HH:MM:SS` from call start.
  - `transcript_text()` → speaker-labeled, timestamped lines:
    `[00:03:12] Client: …`
  - `finalize(metadata)` → calls MoM generation, returns the MoM dict.
- **Drivers** (mirror `interview_eval/session.py`):
  - `run_live(session, device, host_channel=0, client_channel=1, render_fn)` —
    background segmenter thread + main-thread live panel; Ctrl+C to end. **Direct
    reuse of the proven `run_live` structure.**
  - `run_simulated(session, wav_path)` — offline stereo-WAV replay.

---

## 4. MoM generation & format

### 4.1 Schema (extend the existing one)
Start from `MOM_SCHEMA_KEYS` and tune for a **client-facing** document:
```
meetingTitle, dateTime, platform='Google Meet', participants[],
agenda[], discussion[{topic, points[]}], decisions[],
actionItems[{task, owner, dueDate, priority}],
risks[], dependencies[], openQuestions[],
nextSteps[],            # NEW — explicit, client-facing
summary[]               # 5–8 line executive overview
```
The generator prompt is updated to: (a) ingest a **speaker-labeled** transcript,
(b) attribute `actionItems.owner` to Host / a named client participant when the
transcript makes it clear, (c) stay strictly grounded ("use ONLY facts in the
transcript; never invent owners/dates") — keeping `mom_generate`'s existing
anti-hallucination guardrails.

### 4.2 Rendering (client-grade)
- **Markdown** — refine the existing `render_markdown` for a polished,
  professional layout with a clean header block (Title / Date / Attendees /
  Prepared by). Deterministic, no second LLM call.
- **Optional HTML** — Markdown→HTML for a tidy email body / attachment
  (lightweight; library TBD, e.g. `markdown` package).
- **Optional PDF** — deferred to a follow-up unless required (see Decision C).

### 4.3 Model
Existing default is `MOM_MODEL = "gpt-4o-mini"`. For **high-end clients**,
recommend bumping the MoM model to **`gpt-4o`** (better synthesis/attribution)
via a `--model` flag, default configurable. Whisper stays `whisper-1`.

---

## 5. Sharing "after the call"

Pipeline at `finalize`:
1. **Always:** save bundle to `~/meeting-mom/<timestamp>_<slug>/` —
   `transcript.txt`, `mom.json`, `mom.md` (+ `mom.html` if enabled), `meeting.json`.
2. **Always:** copy `mom.md` to clipboard (pyperclip, already a dep).
3. **Optional share (Decision B):** create a **Gmail draft** addressed to the
   participant emails, subject `Minutes of Meeting — <title> (<date>)`, body =
   rendered MoM (HTML or Markdown). **Draft only — never auto-send.** Sending a
   client-facing email is outward-facing; the user reviews and hits send. (Uses
   the available Gmail integration; gated behind an explicit `--email-draft` flag
   + on-screen confirmation.)

---

## 6. CLI surface (`meet-mom`)

```bash
# Verify routing (same as hire-eval)
meet-mom list-devices
meet-mom check-audio --device "hire-eval input Device"

# Live client meeting → MoM
meet-mom record \
  --device "hire-eval input Device" \
  --title "Acme Q3 Roadmap Review" \
  --participants "You (Host); Jane Doe (Acme, VP Product); ..." \
  --agenda agenda.txt \           # or --meeting meeting.yaml
  --model gpt-4o \
  --email-draft                   # optional: open a Gmail draft to attendees

# Offline test (no call, no hardware)
meet-mom simulate --wav /tmp/test.wav --title "Test Sync"

# Already have a transcript? skip audio entirely
meet-mom from-transcript --file transcript.txt --title "..."
```
Meet setup is identical to `hire-eval run`: **Meet Speaker = `hire-eval out
Device`**, headphones on. Same consent banner prints on start (recording a client
call — get consent).

---

## 7. Testing strategy (mirror hire-eval: 29 tests, all mocked)

- **Pure-core unit tests** (`tests/test_meeting_mom.py`), no hardware/API:
  - `MeetingSession` builds correct ordered, timestamped, speaker-labeled
    transcript from injected utterances (mock `transcribe_fn`).
  - Timestamp formatting from sample counts.
  - `mom.py` renderers: golden-output Markdown for a known MoM dict; schema
    key-completion (reuse `mom_generate`'s key-filling).
  - `share.py`: file bundle written correctly to a tmp dir; Gmail draft builder
    produces correct recipients/subject/body **with the Gmail call mocked**
    (no real email).
- **Offline E2E:** `meet-mom simulate` against a synthesized two-voice WAV from a
  small `scripts/make_test_meeting.py` (clone of `make_test_interview.py`, with
  host/client lines) — but with the OpenAI calls mocked in the test, and a manual
  smoke-run documented for real verification.
- Target parity with hire-eval: all tests mocked, no API key or mic required to
  run `pytest`.

---

## 8. Locked decisions ✅ (2026-06-11)

- **Decision A — Code layout: A1 (pragmatic).** `meeting_mom` imports the audio
  engine from `interview_eval` as-is. No edits to existing code → zero risk to the
  29 passing hire-eval tests. (`audio_core` refactor stays a future follow-up.)
- **Decision B — Sharing: Gmail draft + file + clipboard.** Always save bundle +
  clipboard; additionally create a **Gmail draft** to attendees behind
  `--email-draft`. **Draft only, never auto-send.**
- **Decision C — Format: Markdown + HTML.** Polished Markdown for clipboard/file;
  clean HTML for the email body. PDF deferred.
- **Decision D — MoM model: `gpt-4o` default**, `--model` to override (e.g. back to
  `gpt-4o-mini` for cheap runs). Whisper stays `whisper-1`.

### Round 2 (post-build)
- **Speaker ID: roster attribution only** (no diarization for now). Transcript is
  Host/Client; owners attributed from context + roster. (Local pyannote
  "name-later" diarization parked as a future option.)
- **Pre-flight: auto from Google Calendar.** A `/mom` command (in
  `.claude/commands/mom.md`) has Claude pull title/attendees/agenda from Calendar,
  switch audio, launch `meet-mom record`, and create a Gmail draft post-call.
- **Audio switching: automated via `switchaudio-osx`** (installed) — Claude flips
  output to `hire-eval out Device` before recording and restores it after.
- **Work-only minutes:** the MoM prompt explicitly excludes greetings, small talk,
  and off-topic chatter; only substantive work content is recorded.

---

## 9. Build order (once decisions are locked)

1. Scaffold `src/meeting_mom/` + `meet-mom` entry in `pyproject.toml`; wire
   `list-devices`/`check-audio` re-exports. *(smoke: `meet-mom list-devices`)*
2. `meeting.py` metadata model + `meeting.yaml`/flags loading.
3. `MeetingSession` core + `run_simulated` driver; unit tests for the transcript.
4. `mom.py` — speaker-aware generation + Markdown/HTML renderers; renderer tests.
5. `share.py` — file bundle + clipboard; Gmail-draft builder (mocked in tests).
6. `run_live` driver + optional live transcript panel.
7. `scripts/make_test_meeting.py` + offline `simulate` E2E; full `pytest` green.
8. Docs: `docs/MEETING_MOM.md` usage guide; link from `GETTING_STARTED.md`.
9. Manual smoke on a real/test Meet call; iterate on MoM prompt quality.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Multiple client speakers can't be separated by channel | Be explicit; roster + best-effort owner attribution; ML diarization deferred |
| LLM invents owners/dates/decisions | Keep `mom_generate`'s strict "facts-only" system prompt; speaker labels reduce misattribution |
| Long calls → large transcript / token cost | Chunked summarization fallback for very long transcripts (note for v2); `gpt-4o` 128k handles most calls |
| Accidentally emailing a client a draft MoM | Draft-only, never auto-send; explicit flag + confirmation |
| Breaking the working hire-eval tool | A1 layout = no edits to `interview_eval`; rerun its 29 tests in CI anyway |
| Recording consent / privacy | Consent banner on start; user owns disclosure to client |
