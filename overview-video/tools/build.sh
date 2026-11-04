#!/usr/bin/env bash
# Build one episode segment end to end.
# usage: tools/build.sh ep01_intro            (full build)
#        tools/build.sh ep01_intro --no-tts   (reuse existing voice files)
set -euo pipefail
cd "$(dirname "$0")/.."
EP="$1"; OUT="build/$EP"
mkdir -p "$OUT"
if [ "${2:-}" != "--no-tts" ]; then python3 tools/tts.py "script/$EP.json" "$OUT"; fi
python3 tools/timeline.py "script/$EP.json" "$OUT"
node tools/render.js "render/$EP.html" "$OUT"
python3 tools/mix.py "$OUT"
ffmpeg -v error -y -framerate 30 -i "$OUT/frames/f%05d.png" -i "$OUT/mix.wav" \
  -c:v libx264 -pix_fmt yuv420p -crf 20 -preset slow -c:a aac -b:a 192k -shortest "$OUT/$EP.mp4"
python3 tools/assemble.py "script/$EP.json" "$OUT"
echo "built $OUT/${EP}_final.mp4"
