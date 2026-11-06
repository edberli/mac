#!/usr/bin/env bash
# One-time setup: Python TTS, voice models, Node packages.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -q --target .pydeps piper-tts numpy opencc-python-reimplemented
mkdir -p .voices
for v in en/en_US/ryan/medium/en_US-ryan-medium en/en_GB/alan/medium/en_GB-alan-medium en/en_US/lessac/medium/en_US-lessac-medium; do
  n=$(basename "$v")
  for ext in onnx onnx.json; do
    f=".voices/$n.$ext"
    # download to .part first so an interrupted transfer is never mistaken for a finished file
    [ -f "$f" ] || { curl -fsSL --retry 3 -o "$f.part" "https://huggingface.co/rhasspy/piper-voices/resolve/main/$v.$ext" && mv "$f.part" "$f"; }
  done
done
npm install --silent
npx playwright install chromium   # headless browser used by tools/render.js
echo "setup done"
echo "Also needed: ffmpeg (Mac: brew install ffmpeg) and MINIMAX_API_KEY in your environment for voices."
