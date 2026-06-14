#!/usr/bin/env bash
# Save/restore the macOS system audio OUTPUT device around a meet-mom recording,
# so we never leave the system stuck on the Multi-Output ("hire-eval out Device").
#
# Usage:
#   scripts/mom_audio.sh arm      # save current output, switch to the BlackHole tap
#   scripts/mom_audio.sh restore  # switch back to whatever was saved by `arm`
#   scripts/mom_audio.sh status   # print current output device
#
# The prior device is remembered in a state file, so `restore` returns to your
# real device (BenQ / Speakers / headphones) rather than a hardcoded guess.
set -euo pipefail

TAP_DEVICE="${MOM_TAP_DEVICE:-hire-eval out Device}"   # Multi-Output (speakers + BlackHole)
FALLBACK_DEVICE="${MOM_FALLBACK_DEVICE:-MacBook Pro Speakers}"
STATE_DIR="${HOME}/.meeting-mom"
STATE_FILE="${STATE_DIR}/prev_output"

if ! command -v SwitchAudioSource >/dev/null 2>&1; then
  echo "SwitchAudioSource not found. Install with: brew install switchaudio-osx" >&2
  exit 1
fi

current() { SwitchAudioSource -c -t output; }

case "${1:-}" in
  arm)
    mkdir -p "${STATE_DIR}"
    cur="$(current)"
    # Don't overwrite the saved device if we're already armed (idempotent).
    if [ "${cur}" != "${TAP_DEVICE}" ]; then
      printf '%s' "${cur}" > "${STATE_FILE}"
    fi
    SwitchAudioSource -s "${TAP_DEVICE}" -t output >/dev/null
    echo "Armed: output → '${TAP_DEVICE}' (was '${cur}', saved for restore)."
    ;;
  restore)
    target="${FALLBACK_DEVICE}"
    if [ -f "${STATE_FILE}" ]; then
      saved="$(cat "${STATE_FILE}")"
      [ -n "${saved}" ] && target="${saved}"
    fi
    SwitchAudioSource -s "${target}" -t output >/dev/null \
      || SwitchAudioSource -s "${FALLBACK_DEVICE}" -t output >/dev/null
    rm -f "${STATE_FILE}"
    echo "Restored: output → '$(current)'."
    ;;
  status)
    echo "Current output: $(current)"
    ;;
  *)
    echo "Usage: $0 {arm|restore|status}" >&2
    exit 2
    ;;
esac
