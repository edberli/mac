#!/usr/bin/env bash
# Join finished segments into the full episode.
# usage: tools/join.sh out.mp4 seg1.mp4 seg2.mp4 ...
set -euo pipefail
OUT="$1"; shift
ARGS=(); F=""; i=0
for s in "$@"; do ARGS+=(-i "$s"); F+="[$i:v][$i:a]"; i=$((i+1)); done
ffmpeg -v error -y "${ARGS[@]}" -filter_complex "${F}concat=n=$i:v=1:a=1[v][a]" -map "[v]" -map "[a]" \
  -c:v libx264 -pix_fmt yuv420p -crf 20 -preset medium -r 30 -c:a aac -b:a 192k -ar 44100 "$OUT"
echo "joined $OUT"
