# Getting Started with `hire-eval`

A startup guide for anyone setting up the voice interview-evaluation tool from
scratch on a new macOS machine. Budget ~20 minutes (most of it is the one-time
audio routing).

`hire-eval` listens to both sides of a Google Meet call, transcribes them
(Whisper), scores the candidate's answers against competencies parsed from a job
description (GPT-4o), and writes a weighted Markdown/JSON report. Speaker
separation is done by **hardware channels**, not ML — your mic is channel 0, the
candidate (tapped from Meet via a virtual cable) is channel 1.

> The same audio routing powers **`meet-mom`**, which turns a client Meet call
> into a polished Minutes of Meeting. Once the devices below are set up, see
> [`MEETING_MOM.md`](MEETING_MOM.md).

---

## 1. Prerequisites

- **macOS** (uses CoreAudio + the `say` command)
- **Python 3.10+**
- **ffmpeg** — `brew install ffmpeg`
- **An OpenAI API key** with access to Whisper + GPT-4o

## 2. Install the tool

```bash
cd /Users/mohitchand/Python/speech_text
python -m venv .venv
source .venv/bin/activate
pip install -e .            # installs the `hire-eval` entrypoint
```

Verify:

```bash
hire-eval --help
pytest tests/ -q           # expect 29 passed — confirms the build is healthy
```

## 3. Add your API key

Put it in a `.env` file at the repo root (already gitignored):

```bash
echo 'OPENAI_API_KEY="sk-proj-your-key"' > .env
```

(Alternatively `export OPENAI_API_KEY=...` or pass `--api-key` once — it persists
to the macOS Keychain.)

## 4. Try it with NO hardware — offline simulate

Before touching audio drivers, confirm the brain works. This synthesizes a
two-voice interview WAV and runs the full scoring pipeline:

```bash
python scripts/make_test_interview.py /tmp/test.wav     # ~50s, uses `say`
hire-eval simulate \
  --jd examples/jd.txt --questions examples/questions.yaml \
  --wav /tmp/test.wav --candidate "Test Candidate"
```

You should see the JD parsed into weighted competencies, a competency-alignment
printout (e.g. `api-design → python-api-design`), per-answer scores with evidence
quotes, and an overall hire band. If that works, the tool is good — everything
left is just getting live audio into it.

---

## 5. One-time audio routing (for live calls)

Live mode needs a **virtual audio cable** so the tool can hear the candidate
coming out of Meet. We use [BlackHole](https://github.com/ExistentialAudio/BlackHole).

### 5a. Install BlackHole

```bash
brew install blackhole-2ch
```

**Restart your Mac** afterward so the driver registers. Then confirm:

```bash
hire-eval list-devices     # "BlackHole 2ch" should appear
```

### 5b. Build two devices in Audio MIDI Setup

Open **Audio MIDI Setup** (`/Applications/Utilities/`). Use the **`+`** button
(bottom-left) to create each. Names are cosmetic — only the *input* device's name
gets passed to `--device`, so pick something you'll recognize:

1. **Aggregate Device** — the tool's **INPUT**.
   Check ✅ **your Mac microphone FIRST**, then ✅ **BlackHole 2ch**.
   Channel order matters: mic = ch0 (you), BlackHole = ch1 (candidate).
   *(Example name used in this repo: `hire-eval input Device`.)*

2. **Multi-Output Device** — Meet's **SPEAKER** output.
   Check ✅ **your speakers/headphones** + ✅ **BlackHole 2ch**.
   This lets you hear the candidate while BlackHole simultaneously taps them.
   *(Example name: `hire-eval out Device`.)*

### 5c. Verify the channels

```bash
# Set System Settings → Sound → Output to your Multi-Output device first,
# then run:
hire-eval check-audio --device "hire-eval input Device" --seconds 12
```

Speak → **ch0** rises (you). Play any audio → **ch1/ch2** rise (candidate via
BlackHole). If ch1 stays at 0.0000, your system output isn't pointed at the
Multi-Output device, or BlackHole isn't a member of it.

> **Wear headphones** during real calls. Otherwise speaker audio bleeds into the
> mic (ch0) and muddies speaker separation.

For full routing diagrams and the `conduct`-mode 2nd-cable setup, see
[`AUDIO_SETUP.md`](AUDIO_SETUP.md).

---

## 6. Run a real interview

In **Meet → Settings → Audio**: set **Speaker = your Multi-Output device**, leave
**Microphone = your normal mic**.

```bash
hire-eval run \
  --device "hire-eval input Device" \
  --jd examples/jd.txt \
  --questions examples/questions.yaml \
  --candidate "Jane Doe"
```

- **Ctrl+C** ends the session → report saved to `~/hire-eval/<timestamp>_interview/`.
- Drop `--questions` for **freeform** mode: ask whatever you want aloud; each
  answer is scored only against the competencies it actually addresses.

### The four modes

| Mode | Who asks questions | When to use |
|---|---|---|
| `run` | **You** ask aloud; AI scores silently | Default — start here |
| `run` (freeform) | You ask, no `questions.yaml` | Unstructured / conversational interviews |
| `conduct` | **AI** voices questions (OpenAI TTS) | Hands-off; needs a 2nd BlackHole cable (see AUDIO_SETUP.md) |
| `simulate` | Offline replay of a stereo WAV | Testing without a live call |

---

## 7. Customize for a role

- Edit **`examples/jd.txt`** with the real job description.
- Edit **`examples/questions.yaml`** with your question bank (each tagged to a
  competency label).
- **Delete `competencies.json`** to force a fresh JD parse. Parsing is
  non-deterministic, so **parse once and reuse the same `competencies.json`
  across all candidates** for a fair, apples-to-apples comparison.
- Run a quick `simulate` after editing to sanity-check the weights and that your
  question labels align to JD competencies.

---

## 8. Before any real call

- **Get consent** — tell the candidate you're recording/transcribing (the tool
  also prints a consent reminder on start).
- Scores are **decision support, not a verdict.** Always read the evidence quotes
  and apply your own judgment.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `BlackHole 2ch` not in `list-devices` | Driver didn't register — restart again, or reinstall the `.pkg`. |
| `check-audio` ch1 stays 0.0000 | System/Meet output isn't set to the Multi-Output device, or BlackHole isn't a member of it. |
| Both channels identical | You're missing headphones — speaker audio is bleeding into the mic. |
| `ffmpeg: command not found` | `brew install ffmpeg`. |
| Competency labels don't map to JD | Check the alignment printout at startup; rename `questions.yaml` labels closer to the JD wording. |
