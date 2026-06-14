# Session Handoff — hire-eval (resume after restart)

**Last updated:** 2026-06-10, before a restart to finish BlackHole audio-driver install.

## TL;DR — where we are
The **`hire-eval` interview-evaluation tool is fully built and tested (29/29 passing).**
The only thing left is the **macOS audio routing setup** so it can hear both
sides of a Google Meet call. We were mid-install of **BlackHole** (the virtual
audio driver) and need a **restart** for it to register.

## ▶ FIRST THING TO DO AFTER RESTART
Confirm BlackHole installed, then build two audio devices. Run:
```bash
cd /Users/mohitchand/Python/speech_text && source .venv/bin/activate
hire-eval list-devices        # expect to now see "BlackHole 2ch"
```
- If **BlackHole 2ch shows up** → go to "Build the two devices" below.
- If **it does NOT** show up → the install didn't complete. Re-run:
  `! brew install blackhole-2ch` (the installer GUI also lives at
  `~/Library/Caches/Homebrew/Cask/BlackHole2ch-0.6.1.pkg--0.6.1.pkg` — double-click it),
  enter your Mac password, and restart again.

---

## What is built (no work needed — done & tested)

`hire-eval` is a voice interview evaluator: it transcribes both sides of a Meet
call (Whisper), scores the candidate's answers against competencies parsed from a
Job Description (GPT-4o), and writes a weighted report. Installed as an editable
package (`pip install -e .`), entrypoint **`hire-eval`**.

### Four modes
| Command | Who asks questions | Notes |
|---|---|---|
| `run` | **You** ask aloud; AI scores silently | Recommended for first real call |
| `conduct` | **AI** voices questions (OpenAI TTS); you pace with keyboard | Needs 2 BlackHole cables |
| `simulate` | Offline replay of a stereo WAV | Testing without a live call |
| `run`/`simulate` **freeform** | You ask, **no questions.yaml needed** | Omit `--questions`; your spoken question anchors scoring |

### Package layout (`src/interview_eval/`)
- `cli.py` — entrypoint, subcommands `list-devices` / `check-audio` / `run` / `simulate` / `conduct`
- `audio_router.py` — device discovery, `UtteranceSegmenter`, `SimulatedSource`, output-device helpers
- `jd_parser.py` — JD → weighted competencies (cached to `competencies.json`)
- `question_bank.py` — `questions.yaml` loading, embedding match, **competency alignment** (token-overlap + embedding)
- `scorer.py` — per-answer 1–10 with evidence quotes; `only_relevant` for freeform
- `report.py` — weighted overall + hire bands + Markdown/JSON
- `session.py` — `InterviewSession` core + `run_live` / `run_simulated` / `run_conduct`
- `tts.py` — OpenAI tts-1 (+ `say` fallback), plays to a device or default
- `dialogue.py` — adaptive follow-up question generation
- `llm.py` — shared OpenAI client (chat JSON/text, embeddings, retry)
- `display.py` — rich live TUI
- Docs: `docs/AUDIO_SETUP.md` (full routing), this file
- Examples: `examples/jd.txt`, `examples/questions.yaml`
- Tests: `tests/test_interview_eval.py` (29 tests, all mocked — no API/hardware)
- Helper: `scripts/make_test_interview.py` (synthesizes a 2-voice test WAV via `say`)

### Verify build still green any time
```bash
pytest tests/ -q                 # expect 29 passed
```

### Key design decisions already made & implemented
- **Speaker separation by hardware channels** (mic = ch0, candidate/BlackHole = ch1) — no ML diarization.
- **Competency alignment**: question-bank labels (e.g. `api-design`) auto-map to JD slugs (e.g. `python-api-design`) via token-overlap, embedding fallback. Printed at startup so mis-maps are visible.
- **conduct capture is echo-safe + push-to-advance**: mic muted while AI speaks; answer = audio between AI's question and your Enter press (fixed an off-by-one + echo bug).
- **freeform** scores each answer only against competencies it actually addresses (`only_relevant=True`), so answers aren't penalized on unrelated competencies.

---

## Build the two audio devices (after BlackHole shows up)

Open **Audio MIDI Setup** (`/Applications/Utilities/`). Use the **`+` button
(bottom-left)** to create each:

1. **Multi-Output Device** — check ✅ **MacBook Pro Speakers** (or headphones) + ✅ **BlackHole 2ch**.
   *(This is Meet's SPEAKER output: you hear the candidate AND BlackHole taps them.)*
2. **Aggregate Device** — check ✅ **MacBook Pro Microphone** FIRST, then ✅ **BlackHole 2ch**.
   *(Mic = channel 0 = you; BlackHole = channel 1 = candidate. This is the tool's INPUT.)*

> For **conduct** mode only, you also need a 2nd cable: `brew install blackhole-16ch`,
> set Meet's **microphone** to "BlackHole 16ch" (AI voice goes there). Not needed for `run`.

### Verify the routing (I can run these for you)
```bash
hire-eval list-devices
hire-eval check-audio --device "Aggregate Device"
# Speak → one channel's RMS bar jumps (you, ch0).
# Play any audio through Meet/speakers → a DIFFERENT channel jumps (candidate, ch1).
# Use HEADPHONES to avoid feedback.
```

---

## Run a real interview (after devices verified)

**Mode A — `run` (you ask, AI scores) — start here**
1. Meet → Settings → Audio: **Speaker = Multi-Output Device**, **Microphone = your normal mic**.
2. ```bash
   hire-eval run --device "Aggregate Device" \
     --jd examples/jd.txt --questions examples/questions.yaml \
     --candidate "Jane Doe"
   ```
   - Freeform variant (no question file): drop `--questions`.
   - Ctrl+C ends → report saved to `~/hire-eval/<timestamp>_interview/`.

**Mode B — `conduct` (AI voices questions)** — see `docs/AUDIO_SETUP.md`; rehearse first:
```bash
hire-eval conduct --dry-run --jd examples/jd.txt --questions examples/questions.yaml --voice nova
```

---

## Before a real call (reminders)
- Customize `examples/jd.txt` + `examples/questions.yaml` for the role; delete
  `competencies.json` to force a fresh JD parse; run a `simulate` to sanity-check
  weights + alignment. (JD parse is non-deterministic — cache it and reuse the
  same `competencies.json` across all candidates for fair comparison.)
- Tell the candidate you're recording/transcribing (tool prints a consent reminder).
- Wear **headphones** to prevent capture feedback.

## Environment facts
- API key: in `.env` (`OPENAI_API_KEY`) — already working.
- Python venv: `.venv` (activate before running; `hire-eval` lives there).
- Platform: macOS (darwin), zsh. Current devices BEFORE BlackHole: iPhone Mic,
  MiniMoo Mic, MacBook Pro Mic, MacBook Pro Speakers, Microsoft Teams Audio.
- BlackHole pkg (if reinstall needed):
  `~/Library/Caches/Homebrew/Cask/BlackHole2ch-0.6.1.pkg--0.6.1.pkg`
