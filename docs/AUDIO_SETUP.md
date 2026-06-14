# Audio Setup for `hire-eval` (macOS)

`hire-eval` captures **both sides** of a Google Meet call and keeps them on
**separate channels** so it knows who said what — your mic is the interviewer,
Meet's output is the candidate. This needs a one-time macOS audio setup using
the free **BlackHole** virtual audio device.

```
Built-in Mic (you) ─────────────┐
                                 ├──> Aggregate Device ──> hire-eval  (INPUT)
Meet output ─> BlackHole 2ch ────┘        ch0 = you, ch1+ = candidate

Meet output ─> Multi-Output Device ─> your speakers (so you still hear it)
                                    └─> BlackHole 2ch (so hire-eval taps it)
```

## 1. Install BlackHole
```bash
brew install blackhole-2ch
```

## 2. Create a Multi-Output Device (so you still HEAR the candidate)
Open **Audio MIDI Setup** (`/Applications/Utilities`):
1. Click **+** (bottom-left) → **Create Multi-Output Device**.
2. Check **both**: your headphones/speakers **and** **BlackHole 2ch**.
3. Rename it e.g. "Meet + BlackHole".

## 3. Create an Aggregate Device (what hire-eval RECORDS)
1. Click **+** → **Create Aggregate Device**.
2. Check **both**: **Built-in Microphone** (or your interview mic) **and**
   **BlackHole 2ch**. Order matters — put the **mic first** so it lands on
   channel 0.
3. Rename it e.g. "Interview Capture".

## 4. Route Meet's audio
During the call, set your **system output** (or Chrome/Meet output) to the
**Multi-Output Device** from step 2. You'll still hear the candidate, and
BlackHole will receive a copy.

## 5. Verify the routing
```bash
hire-eval list-devices          # find the index/name of "Interview Capture"
hire-eval check-audio --device "Interview Capture"
```
While it records: **speak** (one channel's RMS bar should jump) and **play some
audio through Meet/your speakers** (a *different* channel should jump). You want
**ch0 = your voice** and **ch1 = the candidate/Meet playback**. If only one
channel exists, your Aggregate Device isn't set up correctly.

If your mic isn't on ch0, pass the right channels to `run`:
```bash
hire-eval run --device "Interview Capture" \
  --interviewer-channel 0 --candidate-channel 1 \
  --jd examples/jd.txt --questions examples/questions.yaml
```

---

# AI-Interviewer (`conduct`) Setup — AI voices questions to the candidate

In `conduct` mode the AI **speaks** each question to the candidate, so the spoken
audio must go **into** Meet as your microphone. That needs a **second** virtual
cable (in addition to the one tapping Meet's output), so install both BlackHole
variants:

```bash
brew install blackhole-2ch blackhole-16ch
```

Routing (two independent cables):

```
AI voice (tts) ─> BlackHole 16ch ─> [Meet Microphone]      (candidate hears AI)

Meet output ─> Multi-Output Device ─┬─> your headphones    (you hear candidate)
                                    └─> BlackHole 2ch ─> hire-eval input (scoring)
```

1. **Meet microphone** → set to **BlackHole 16ch**. The tool plays the AI's
   spoken questions here (`--output-device "BlackHole 16ch"`).
2. **Meet output** → set to a **Multi-Output Device** (your headphones +
   **BlackHole 2ch**), so you still hear the candidate while the tool taps it.
3. **hire-eval input** → **BlackHole 2ch** (the candidate's voice)
   (`--input-device "BlackHole 2ch" --candidate-channel 0`).

Note: in `conduct` you do **not** need the Aggregate Device or your real mic —
the AI is the interviewer, so only the candidate is captured for scoring.

Run it:
```bash
hire-eval conduct \
  --jd examples/jd.txt --questions examples/questions.yaml \
  --input-device "BlackHole 2ch" --candidate-channel 0 \
  --output-device "BlackHole 16ch" \
  --voice nova --candidate "Jane Doe"
```
Controls while it runs (press **Enter only after the candidate has finished
answering** — their answer is the audio captured between the AI's question and
your Enter press):

- **Enter / n** — candidate is done → capture & score this answer, ask next question
- **f** — capture so far, then have the AI ask an adaptive follow-up (keep listening)
- **r** — repeat the current question (mic stays muted while the AI speaks)
- **q** — capture final answer, finish, and generate the report

The mic is automatically muted whenever the AI is speaking, so the AI's voice is
never mistaken for the candidate's answer. Add `--no-followups` to ask the bank
verbatim, or `--engine say` to use the free offline voice.

> Verify routing first with `hire-eval list-devices` (now lists both input and
> output devices) and a quick `check-audio` on the BlackHole 2ch input.

### Rehearse without BlackHole (`--dry-run`)

To hear the AI voice and practice the keyboard flow before any audio setup, use
`--dry-run`: the AI plays to your **default speakers** and treats your **default
mic** as the candidate (so you can answer your own questions to test scoring).
Use headphones to avoid the mic picking up the AI voice.

```bash
hire-eval conduct --dry-run \
  --jd examples/jd.txt --questions examples/questions.yaml \
  --voice nova --candidate "Rehearsal"
# tip: add --engine say to rehearse with the free offline voice (no TTS cost)
```

## Troubleshooting
- **No multi-channel device in `list-devices`** → the Aggregate Device wasn't
  created or wasn't given two sub-devices. Redo step 3.
- **Candidate channel silent** → Meet/system output isn't pointed at the
  Multi-Output Device (step 4), or BlackHole isn't checked in it (step 2).
- **Both voices on the same channel** → you selected a *mixed* device; use the
  **Aggregate** device (keeps sub-devices on separate channels), not a
  Multi-Output device, as the input.
