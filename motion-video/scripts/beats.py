"""motion-video · beats.py — analyse a music track so the film can be cut to it.

    uv run --with librosa python beats.py track.mp3 [--len 15] [--drop-at 4.0] [--out beats.json]
    (track: a local file, or mixkit-music:<id> / an https URL — same sources as mix.py)

Prints and writes JSON:
  tempo, beats[], downbeats[] (every 4th beat, phase picked by low-end energy), sections[] (big energy changes),
  drop (the strongest jump in low-band energy, refined to 20 ms — auto beat grids can be 2 beats off),
  window: the best [start, start+len] cut of the track for a film of --len seconds, placing the drop at
  --drop-at seconds into the film (default: ~30 % in), with fades that land on bar lines.
Use it to hang state changes on beats, big moments on downbeats, the hero on the drop; then put the same
offset into sound.json (bed.offset, kind "music").
"""
import json
import sys
from pathlib import Path

import librosa
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src = args[0]
L = float(opt("--len", 15))
drop_at = float(opt("--drop-at", L * 0.3))

if ":" in src.split("/")[0] or src.startswith("http"):
    from mix import resolve  # noqa: E402  (shares the asset cache)
    path = resolve(src, Path.cwd())
else:
    path = Path(src)
sr = 22050
y, _ = librosa.load(str(path), sr=sr, mono=True)
dur = len(y) / sr
tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
tempo = float(np.atleast_1d(tempo)[0])

# low-band energy envelope (where kicks and drops live)
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
low = S[freqs < 150].sum(axis=0)
t_env = librosa.times_like(low, sr=sr, hop_length=512)
lowdb = 20 * np.log10(low + 1e-9)

# downbeats: of the 4 possible phases, the one whose beats carry the most low-end
beat_low = np.interp(beats, t_env, lowdb) if len(beats) else np.array([])
phase = int(np.argmax([beat_low[p::4].mean() if len(beat_low[p::4]) else -1e9 for p in range(4)])) if len(beats) >= 8 else 0
downbeats = beats[phase::4]

# sections & drop: compare 4 s of low-band energy after vs before each downbeat
def lvl(a, b):
    m = (t_env >= a) & (t_env < b)
    return float(lowdb[m].mean()) if m.any() else -120.0
jumps = sorted(((lvl(b, b + 4) - lvl(b - 4, b), float(b)) for b in downbeats if 4 <= b <= dur - 4), reverse=True)
sections = sorted(b for _, b in jumps[:4])
drop = jumps[0][1] if jumps else float(beats[len(beats) // 3]) if len(beats) else 0.0
# refine: the steepest 20 ms rise of low-band energy within ±0.3 s
fine = np.arange(max(0, drop - 0.3), min(dur, drop + 0.3), 0.02)
e = [np.mean(np.square(y[int(t * sr): int((t + 0.02) * sr)])) for t in fine]
if len(e) > 1:
    drop = float(fine[int(np.argmax(np.diff(10 * np.log10(np.array(e) + 1e-12)))) + 1])

start = max(0.0, min(drop - drop_at, dur - L))
bar = 4 * 60 / tempo if tempo else 2.0
res = {
    "file": str(path), "duration": round(dur, 2), "tempo": round(tempo, 1), "bar": round(bar, 3),
    "beats": [round(float(b), 3) for b in beats], "downbeats": [round(float(b), 3) for b in downbeats],
    "sections": [round(s, 2) for s in sections], "drop": round(drop, 3),
    "window": {"start": round(start, 3), "end": round(start + L, 3), "drop_in_film": round(drop - start, 3),
               "beats_in_film": [round(float(b) - start, 3) for b in beats if start <= b < start + L],
               "downbeats_in_film": [round(float(b) - start, 3) for b in downbeats if start <= b < start + L]},
}
out = opt("--out", "beats.json")
Path(out).write_text(json.dumps(res, indent=1))
w = res["window"]
print(f"{path.name}: {dur:.1f} s, {tempo:.0f} BPM (bar {bar:.2f} s), drop @ {drop:.2f} s, sections {res['sections']}")
print(f"cut {w['start']:.2f}–{w['end']:.2f} s → drop at {w['drop_in_film']:.2f} s in the film; "
      f"{len(w['beats_in_film'])} beats, downbeats at {w['downbeats_in_film'][:8]}… → {out}")
