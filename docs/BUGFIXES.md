# Bug Fixes — Refactor Hardening (2026-06-14)

This document records the bugs discovered while verifying the technical-debt
refactor described in `CODEBASE_REVIEW.md`, and how each was fixed. The refactor
itself (LLM unification, `MoMGenerator` base class, shared `UtteranceSegmenter`,
hardware/API guards) was sound, but it was committed without running the test
suite, which let two runtime-breaking regressions and some smaller issues slip in.

**Baseline at discovery:** `pytest` reported `2 failed, 32 passed, 1 collection error`.
**After fixes:** `56 passed`.

---

## 🔴 BUG-1 — `NameError` in `audio_router.utterance_to_wav` (runtime crash)

- **Severity:** Critical (crashes a live interview, not just tests)
- **File:** `src/interview_eval/audio_router.py:38-39`
- **Introduced by:** Recommended #4 (promoting `_preprocess_audio`/`_array_to_wav`
  to public `preprocess_audio`/`array_to_wav` in `live_capture.py`).

### Root cause
The rename updated the **import** but not the **call sites**:

```python
# line 23 (updated): from mom_pipeline.live_capture import preprocess_audio, array_to_wav
cleaned = _preprocess_audio(...)   # ← old name, no longer defined  → NameError
return _array_to_wav(cleaned, ...) # ← old name
```

`utterance_to_wav` is on the live interview path (`session.py:397`) and the
`--simulate` path, so this raised `NameError: name '_preprocess_audio' is not
defined` at runtime, not only under test.

### Fix
Updated the two call sites to the new public names. (Commit grep confirms no
remaining `_preprocess_audio` / `_array_to_wav` references in `src/` or `tests/`.)

### Prevention
A pre-commit `pytest` run catches this immediately — both
`test_run_simulated_end_to_end` and `test_run_conduct_is_echo_safe_and_captures_answer`
exercise this path.

---

## 🔴 BUG-2 — `test_meeting_mom.py` collection ImportError (13 tests lost)

- **Severity:** Critical (entire test module fails to import)
- **File:** `src/meeting_mom/mom.py` / `tests/test_meeting_mom.py:9`
- **Introduced by:** Recommended #3 (generalizing MoM generation into the
  `MoMGenerator` / `ClientMoMGenerator` class hierarchy).

### Root cause
The refactor moved `_normalize` and `_system_prompt` from module-level functions
into `ClientMoMGenerator` methods, deleting the module-level names. The existing
test imported them directly:

```python
from meeting_mom.mom import MOM_SCHEMA_KEYS, render_html, render_markdown, _normalize, _system_prompt
# ImportError: cannot import name '_normalize' from 'meeting_mom.mom'
```

Because the import failed at module load, **all** tests in `test_meeting_mom.py`
were silently dropped from the run — a much bigger blast radius than the two
functions actually touched.

### Fix
Restored the module-level public surface as thin shims that delegate to a single
shared generator, preserving one source of truth while keeping back-compat:

```python
_DEFAULT_GENERATOR = ClientMoMGenerator()

def _system_prompt() -> str:
    return _DEFAULT_GENERATOR.build_system_prompt()

def _normalize(mom: Dict, meeting: Meeting) -> Dict:
    return _DEFAULT_GENERATOR.normalize(mom, meeting)
```

### Prevention
When a refactor changes a module's exported names, update callers/tests in the
same change. Running `pytest` surfaces collection errors before commit.

---

## 🟡 BUG-3 — Untested `generate_mom` despite the review calling for it

- **Severity:** Medium (coverage gap; the review's Critical #3 explicitly asked
  for a `generate_mom` test)
- **File:** `tests/test_meeting_mom.py`

### Root cause
The refactor added a `client` injection point to `generate_mom` (designed for
mocking) but no test actually exercised the `prompt → API → JSON → normalize`
flow. The function's parsing/normalization path was unverified.

### Fix
Added two direct tests against a mocked OpenAI client:
- `test_generate_mom_parses_and_normalizes` — model fields survive, schema is
  completed, missing `dateTime`/`participants` fall back to meeting metadata.
- `test_generate_mom_recovers_from_unparseable_response` — a non-JSON reply
  degrades to a schema-complete empty MoM instead of crashing.

---

## 🟢 BUG-4 — Duplicate / unused imports in `live_capture.py`

- **Severity:** Low (lint debt, no runtime effect)
- **File:** `src/mom_pipeline/live_capture.py:2-11`

### Root cause
The edit re-added `import queue` / `import time` (already present) and pulled in
`shutil`, `subprocess`, `tempfile`, `pathlib.Path` — none of which are used in
this module (they belong to `interactive.py`'s TTS path).

### Fix
Removed the duplicate and unused imports.

---

## Behavioral note (not a bug, but worth tracking)

`stream_audio_auto_stop` now delegates stop-detection to the shared
`UtteranceSegmenter`. This changes the semantics of `min_capture`: previously it
gated on **wall-clock time since stream start** (including leading silence); the
segmenter's `min_utterance` measures **captured speech since onset**. The new
behavior is arguably more correct (it ignores dead air before the user speaks),
but it is a behavior change. The segmenter also maintains its own audio buffer
while `live_capture` keeps `audio_data` separately — the segmenter's emitted
array is discarded and it is used only as a stop signal (minor double-buffering;
acceptable).

---

## Verification

```bash
pytest tests/ -q
# 56 passed
```
