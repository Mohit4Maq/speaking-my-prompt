# `meet-mom` — Client-Meeting Minutes from Google Meet

Capture both sides of a Google Meet call and auto-generate a polished **Minutes
of Meeting** (MoM) that you can save, copy, and email to attendees. Reuses the
exact same audio routing as `hire-eval` (see [`AUDIO_SETUP.md`](AUDIO_SETUP.md)).

- **Host = channel 0** (your mic), **Client side = channel 1** (everyone on the
  Meet call, tapped via BlackHole). Speaker separation is by hardware channel.
- Transcription: Whisper (`whisper-1`). MoM synthesis: **`gpt-4o`** by default.
- Design notes: [`MEETING_MOM_PLAN.md`](MEETING_MOM_PLAN.md).

> **Limitation:** all client-side participants arrive as one mixed Meet stream, so
> the transcript labels are **Host / Client**, not per-person. Provide a roster
> via `--participants`; the model attributes action-item owners to a named person
> when the transcript makes it clear, otherwise to the side.

> **Work-only minutes:** greetings, small talk, and off-topic chatter (world news,
> weather, sports, family/personal life, connection issues) are **excluded** — the
> MoM captures only substantive work content (topics, decisions, commitments,
> risks, follow-ups).

> **⚠ Headphones are required for reliable speaker attribution.** Without them,
> the client's voice plays through your speakers and bleeds into your mic (ch0),
> so client speech gets mislabeled as Host. The *content* still survives (the
> client channel is a clean digital tap), but **who-said-what / action-item owners
> become unreliable.** A live test confirmed bleed at speaker volume floods the
> Host channel — a silence threshold can't filter speech-level bleed. Use any
> headphones (even one earbud) for client calls where attribution matters.

---

## The one-command flow (recommended): `/mom`

You don't have to run the CLI by hand. In Claude Code, just run **`/mom`** (optionally
`/mom next` or `/mom <title>`). Claude then:

1. Reads your **Google Calendar** event → pulls title, attendees + emails, agenda.
2. Confirms the details with you.
3. Switches your Mac output to `hire-eval out Device` (via `switchaudio-osx`) so
   BlackHole taps the call, and reminds you about Meet's speaker + headphones.
4. Starts `meet-mom record` in the background with everything pre-filled.
5. When you say **done**, stops it, generates the MoM, restores your audio, and
   **creates a Gmail draft** to the attendees for your review (never auto-sent).

So your whole prep is: start the call, run `/mom`, say "done" at the end, review
the draft, hit send. Everything below is the manual equivalent.

---

## Setup (one-time)

Identical to `hire-eval`. You need the BlackHole Aggregate + Multi-Output devices
from [`GETTING_STARTED.md`](GETTING_STARTED.md) §5. Verify once:

```bash
meet-mom list-devices
meet-mom check-audio --device "hire-eval input Device"   # ch0=you, ch1=other side
```

In **Meet → Settings → Audio**: Speaker = your **Multi-Output device**
(`hire-eval out Device`), Microphone = your normal mic. **Wear headphones.**

---

## Record a live meeting

```bash
meet-mom record \
  --device "hire-eval input Device" \
  --title "Acme Q3 Roadmap Review" \
  --participants "You (Host) <me@firm.com>; Jane Doe (Acme, VP Product) <jane@acme.com>" \
  --agenda agenda.txt \
  --host-name "Mohit Chand" \
  --email-draft                 # optional: prepare a Gmail draft to attendees
```

A live transcript panel shows Host/Client lines as they're captured. **Ctrl+C**
ends the call → the MoM is generated, printed, saved, and copied to your
clipboard. Output bundle (`~/meeting-mom/<timestamp>_<slug>/`):

| File | Contents |
|---|---|
| `mom.md` | Polished Markdown minutes (also copied to clipboard) |
| `mom.html` | Clean HTML body for an email |
| `mom.json` | Structured MoM (agenda, decisions, action items, …) |
| `transcript.txt` | Full speaker-labeled, timestamped transcript |
| `meeting.json` | The metadata you supplied |
| `email_draft.json` | Draft spec (only with `--email-draft`) |

### Key flags
| Flag | Purpose |
|---|---|
| `--title` | Meeting title (used in the MoM + email subject) |
| `--participants` | `Name (Role) <email>` entries, `;`-separated. Emails enable the draft recipients. |
| `--agenda FILE` | Seed the agenda (one item per line) |
| `--host-name` | Your name → "Prepared by" |
| `--model` | MoM model (default `gpt-4o`; use `gpt-4o-mini` for cheap runs) |
| `--email-draft` | Write an `email_draft.json` spec to the bundle |
| `--cc` | Extra recipient emails (comma/semicolon separated) |
| `--no-clipboard` | Skip copying to clipboard |
| `--output-dir` | Bundle location (default `~/meeting-mom`) |
| `--language` | Spoken language code (default `en`) |

---

## Sharing the minutes (Gmail draft)

`meet-mom` **never sends email** and never auto-creates a draft. With
`--email-draft` it writes `email_draft.json` (recipients, subject, HTML body) to
the bundle. To create the actual Gmail draft:

- **Via Claude:** open the bundle and ask Claude to create a Gmail draft from
  `email_draft.json` — it uses the connected Gmail integration. You review the
  recipients and hit **send** yourself.
- **Manually:** paste `mom.html` (or `mom.md`) into a new email to the attendees.

---

## Test it without a call

```bash
# Synthesize a two-voice meeting WAV, then run the full pipeline offline:
python scripts/make_test_meeting.py /tmp/test_meeting.wav
meet-mom simulate --wav /tmp/test_meeting.wav \
  --title "Acme Q3 Roadmap Review" \
  --participants "You (Host); Jane Doe (Acme, VP Product)"
```

Or generate a MoM from an existing transcript (no audio at all):

```bash
meet-mom from-transcript --file transcript.txt --title "Acme Sync"
```

---

## Before any real call

- **Get consent** — recording/transcribing a client meeting may require all
  participants' agreement (the tool prints a reminder on start).
- The MoM is auto-generated decision support — **review it for accuracy** before
  sending to a client.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Only `ch0` responds in `check-audio` | Meet/system output isn't set to the Multi-Output device, or BlackHole isn't a member of it. See `AUDIO_SETUP.md`. |
| Client side missing from transcript | Meet **Speaker** must be your Multi-Output device so BlackHole taps it. |
| Both channels identical / echoey | Wear headphones — speaker audio is bleeding into the mic. |
| Empty MoM sections | The model only fills from the transcript; short calls yield sparse minutes. |
