#!/usr/bin/env bash
# One-time setup: Python TTS, voice models, Node packages.
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -q --target .pydeps piper-tts numpy
mkdir -p .voices
for v in en/en_US/ryan/medium/en_US-ryan-medium en/en_GB/alan/medium/en_GB-alan-medium en/en_US/lessac/medium/en_US-lessac-medium; do
  n=$(basename "$v")
  [ -f ".voices/$n.onnx" ] || curl -sSL -o ".voices/$n.onnx" "https://huggingface.co/rhasspy/piper-voices/resolve/main/$v.onnx"
  [ -f ".voices/$n.onnx.json" ] || curl -sSL -o ".voices/$n.onnx.json" "https://huggingface.co/rhasspy/piper-voices/resolve/main/$v.onnx.json"
done
npm install --silent
echo "setup done"
