#!/usr/bin/env zsh
# Build macOS app and DMG using py2app and create-dmg.
set -euo pipefail

# Ensure python env is active with deps installed.
pip install -U pip setuptools wheel py2app

# create-dmg is a macOS utility distributed via Homebrew (not pip)
if ! command -v create-dmg >/dev/null 2>&1; then
  echo "Installing create-dmg via Homebrew...";
  brew install create-dmg
fi

# Build .app bundle (full copy for standalone app)
python setup.py py2app

APP_PATH="dist/VoiceToTranscript.app"
DMG_PATH="dist/VoiceToTranscript.dmg"
rm -f "$DMG_PATH"

create-dmg \
  --volname "VoiceToTranscript" \
  --app-drop-link 400 200 \
  "$DMG_PATH" \
  "$APP_PATH"

echo "Built $DMG_PATH"
