"""motion-video · qa/check_video.py — mechanical checks on a rendered MP4 (stdlib + ffmpeg).

    python3 check_video.py out.mp4 [--cuts 3.8,14.2] [--blur 1.6-1.96,3.6-4.1] [--loop]

Reports and fails (exit 1) on:
  tags      video must be yuv420p, limited range, BT.709 primaries/transfer/matrix (else colours shift)
  flashes   single-frame flashes: frame n differs from both neighbours while n−1 ≈ n+1
  pops      a frame difference > 3× its neighbours' that isn't a declared cut (--cuts, ±2 frames)
  frozen    spans > 2 s where nothing changes (outside the last 3 s: the end card may hold; anywhere with --loop)
  loop      (--loop) the seam last frame → frame 0 must look like any other step: a JUMP (position: the seam step
            ≫ the median and its neighbours), a HOLD (a duplicated frame: the comp drew t = T, which is frame 0 again)
            or a SPEED BREAK (velocity into the seam ≠ out of it)
Reports (no fail): share of still frames (rests ≥ 25 % is healthy for a product film), shot-length variation
(coefficient of variation of the spans between big changes; ≥ 0.25 means the rhythm isn't uniform),
fast moves (whole-frame/band shifts > 80 px/frame on a 1080 canvas outside --blur windows strobe — estimated from
row/column projections, so slides, pans and swipes are caught but a small element flying alone is not),
loudness and true peak of the audio track.
"""
import json
import re
import subprocess
import sys

v = sys.argv[1]
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
cuts = [float(x) for x in arg("--cuts", "").split(",") if x]
blur = [tuple(map(float, x.split("-"))) for x in arg("--blur", "").split(",") if x]
loop = "--loop" in sys.argv
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
from framediff import analyse, frames, mad
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
    if run == int(2 * fps) and (loop or i / fps < len(d) / fps - 3):
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

if loop:
    # The seam step (last → 0) should be an ordinary step: like its neighbours d[-1] (into the last frame) and d[1].
    fr = frames(v)
    seam, vin, vout = mad(fr[-1], fr[0]), d[-1], d[1]
    med = sorted(d[1:])[len(d[1:]) // 2]
    near = max(vin, vout)
    if seam > max(2.5 * med, 1.8 * near, 1.5):
        verdict = "JUMP (position differs: the last frame isn't one step before frame 0)"
    elif near > 0.5 and seam < 0.25 * min(vin, vout):
        verdict = "HOLD (a duplicated frame at the seam: design for t in [0, T), not [0, T])"
    elif abs(vin - vout) > max(1.0, 0.5 * near) or abs(seam - (vin + vout) / 2) > max(1.0, 0.6 * near):
        verdict = "SPEED BREAK (motion into the seam differs from motion out of it)"
    else:
        verdict = "ok"
    print(f"loop      {verdict}  seam step {seam:.2f} · into {vin:.2f} · out {vout:.2f} · median {med:.2f}")
    if verdict != "ok":
        fails.append("loop")

# Fast moves: per-band row/column projections of small frames, best integer shift + parabola → px/frame.
def shift(a, b, r):
    """Best shift s (|s| ≤ r) aligning profile b to a, and its residual vs the residual at 0."""
    n = len(a)  # compare over the whole profile, edge-padded: a feature shifted out of the overlap must still count
    res = {s: sum(abs(a[i] - b[min(n - 1, max(0, i + s))]) for i in range(n)) / n for s in range(-r, r + 1)}
    s = min(res, key=res.get)
    off = 0.0
    if -r < s < r:
        l, c, h = res[s - 1], res[s], res[s + 1]
        off = 0.5 * (l - h) / (l - 2 * c + h) if l - 2 * c + h > 0 else 0.0
    return s + off, res[s], res[0]


pw = 108
ph = round(pw * vs["height"] / vs["width"] / 2) * 2
small = frames(v, pw, ph)
unit = 1080 / min(vs["width"], vs["height"]) * vs["width"] / pw  # small px → px on a 1080 canvas
B = 4
def profiles(f):
    cols = [[sum(f[y * pw + x] for y in range(k * ph // B, (k + 1) * ph // B)) / (ph // B) for x in range(pw)] for k in range(B)]
    rows = [[sum(f[y * pw:(y + 1) * pw][k * pw // B:(k + 1) * pw // B]) / (pw // B) for y in range(ph)] for k in range(B)]
    return cols + rows
prof = [profiles(f) for f in small]
in_blur = lambda t: any(a - 1 / fps <= t <= b + 1 / fps for a, b in blur)
fast = []
for i in range(1, len(prof)):
    if d[i] < 1 or i in pops or near_cut(i) or in_blur(i / fps):
        continue
    best = 0.0
    for a, b in zip(prof[i - 1], prof[i]):
        s, rb, r0 = shift(a, b, 24)
        if r0 > 0.8 and rb < 0.35 * r0:  # the shift explains the change: a real move, not a content swap
            best = max(best, abs(s) * unit)
    if best > 80:
        fast.append((i / fps, best))
spans = []
for t, px in fast:
    if spans and t - spans[-1][1] <= 1.5 / fps:
        spans[-1] = (spans[-1][0], t, max(spans[-1][2], px))
    else:
        spans.append((t, t, px))
print("fast      " + ("none" if not spans else ", ".join(f"{a:.2f}–{b:.2f}s (~{px:.0f} px/f)" for a, b, px in spans))
      + "  (> 80 px/frame on a 1080 canvas strobes: add a __meta.blur window, pass it as --blur)")

if any(s["codec_type"] == "audio" for s in info["streams"]):
    a = subprocess.run(["ffmpeg", "-i", v, "-af", "loudnorm=print_format=summary", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = re.search(r"Input Integrated:\s+(-?[\d.]+)", a)
    tp = re.search(r"Input True Peak:\s+([-+]?[\d.]+)", a)
    print(f"audio     {I.group(1) if I else '?'} LUFS, true peak {tp.group(1) if tp else '?'} dBTP")

print("FAIL: " + ", ".join(fails) if fails else "PASS")
sys.exit(1 if fails else 0)
