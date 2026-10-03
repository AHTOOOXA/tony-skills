#!/usr/bin/env bash
# motion-video · qa/sheets.sh — contact sheets to LOOK at (Read the PNGs).
#   bash sheets.sh video.mp4 [strip-times…]
# → <video>.qa/sheet.png  (2 fps overview, 270 px wide frames)
#   <video>.qa/phone.png  (1 fps at 360 px wide = how it reads on a phone)
#   <video>.qa/strip-<t>.png (12 consecutive frames around each fast move you name)
#   <video>.qa/frame0.png (the poster)
set -euo pipefail
v="$1"; shift || true
out="${v%.*}.qa"; mkdir -p "$out"
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$v")
n2=$(python3 -c "import math;print(math.ceil($dur*2))"); rows2=$(( (n2 + 5) / 6 ))
n1=$(python3 -c "import math;print(math.ceil($dur))");   rows1=$(( (n1 + 5) / 6 ))
ffmpeg -y -loglevel error -i "$v" -vf "fps=2,scale=270:-1,tile=6x${rows2}" -frames:v 1 -update 1 "$out/sheet.png"
ffmpeg -y -loglevel error -i "$v" -vf "fps=1,scale=360:-1,tile=6x${rows1}" -frames:v 1 -update 1 "$out/phone.png"
ffmpeg -y -loglevel error -i "$v" -vf "select=eq(n\,0)" -frames:v 1 -update 1 "$out/frame0.png"
for t in "$@"; do
  s=$(python3 -c "print(max(0,$t-0.2))")
  ffmpeg -y -loglevel error -ss "$s" -i "$v" -vf "scale=270:-1,tile=6x2" -frames:v 1 -update 1 "$out/strip-$t.png"
done
echo "→ $out/ (sheet.png, phone.png, frame0.png${*:+, strips})"
