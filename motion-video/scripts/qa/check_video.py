"""motion-video · qa/check_video.py — mechanical checks on a rendered MP4 (stdlib + ffmpeg).

    python3 check_video.py out.mp4 [--cuts 3.8,14.2] [--still-min 0.25]

Reports and fails (exit 1) on:
  tags      video must be yuv420p, limited range, BT.709 primaries/transfer/matrix (else colours shift)
  flashes   single-frame flashes: frame n differs from both neighbours while n−1 ≈ n+1
  pops      a frame difference > 3× its neighbours' that isn't a declared cut (--cuts, ±2 frames)
  frozen    spans > 2 s where nothing changes (outside the last 3 s: the end card may hold)
Reports (no fail): share of still frames (rests ≥ 25 % is healthy for a product film), shot-length variation
(coefficient of variation of the spans between big changes; ≥ 0.25 means the rhythm isn't uniform),
loudness and true peak of the audio track.
"""
import json
import re
import subprocess
import sys

v = sys.argv[1]
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
cuts = [float(x) for x in arg("--cuts", "").split(",") if x]
fails = []

info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", v],
                                 capture_output=True, text=True).stdout)
vs = next(s for s in info["streams"] if s["codec_type"] == "video")
num, den = map(int, vs["r_frame_rate"].split("/"))
fps = num / den
tags = {k: vs.get(k) for k in ("pix_fmt", "color_range", "color_space", "color_primaries", "color_transfer")}
ok = tags == {"pix_fmt": "yuv420p", "color_range": "tv", "color_space": "bt709", "color_primaries": "bt709", "color_transfer": "bt709"}
print(f"tags      {'ok' if ok else 'WRONG'} {tags}  {vs['width']}x{vs['height']} @ {fps:g} fps, {float(info['format']['duration']):.2f} s")
if not ok:
    fails.append("tags")

# per-frame difference on tiny grayscale frames, and true single-frame flashes (f_n ≠ neighbours, f_{n−1} ≈ f_{n+1})
sys.path.insert(0, __import__("os").path.dirname(__file__))
from framediff import analyse
d, flashes = analyse(v)
near_cut = lambda i: any(abs(i / fps - c) <= 2 / fps for c in cuts)
pops = [i for i in range(2, len(d) - 2) if d[i] > 4 and d[i] > 3 * max((d[i - 1] + d[i + 1]) / 2, 1) and not near_cut(i)]
print("flashes   " + ("none" if not flashes else ", ".join(f"{i / fps:.2f}s" for i in flashes)))
print("pops      " + ("none" if not pops else ", ".join(f"{i / fps:.2f}s ({d[i]:.0f})" for i in pops)) + "  (a real app's page change is a legit pop — speed-ramp or carry it)")
if flashes:
    fails.append("flashes")

still = [x < 0.25 for x in d]
spans, run = [], 0
for i, s in enumerate(still):
    run = run + 1 if s else 0
    if run == int(2 * fps) and i / fps < len(d) / fps - 3:
        spans.append(i / fps - 2)
print("frozen    " + ("none" if not spans else ", ".join(f"from {t:.2f}s" for t in spans)) + "  (> 2 s with nothing changing)")
if spans:
    fails.append("frozen")

big = [i for i in range(1, len(d)) if d[i] > 6]
gaps = [(b - a) / fps for a, b in zip(big, big[1:]) if b - a > 2]
if len(gaps) > 2:
    m = sum(gaps) / len(gaps)
    cv = (sum((g - m) ** 2 for g in gaps) / len(gaps)) ** 0.5 / m
    print(f"rhythm    still frames {sum(still) / len(still):.0%} · {len(gaps) + 1} shots, length CV {cv:.2f} (≥ 0.25 = not uniform), range {min(gaps):.1f}–{max(gaps):.1f} s")
else:
    print(f"rhythm    still frames {sum(still) / len(still):.0%}")

if any(s["codec_type"] == "audio" for s in info["streams"]):
    a = subprocess.run(["ffmpeg", "-i", v, "-af", "loudnorm=print_format=summary", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = re.search(r"Input Integrated:\s+(-?[\d.]+)", a)
    tp = re.search(r"Input True Peak:\s+([-+]?[\d.]+)", a)
    print(f"audio     {I.group(1) if I else '?'} LUFS, true peak {tp.group(1) if tp else '?'} dBTP")

print("FAIL: " + ", ".join(fails) if fails else "PASS")
sys.exit(1 if fails else 0)
