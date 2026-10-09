"""motion-video · qa/verify_audio.py — check a mix by measurement (the agent can't listen).

    uv run --with librosa --with pyloudnorm --with soundfile --with scipy --with pedalboard python verify_audio.py sound.json [--hero T]
    … --with matplotlib python verify_audio.py sound.json --png spec.png   # + a spectrogram with events/cues marked

Reads the spec (events, bed, silences) and the WAV it produced. Checks:
  loudness      integrated ≤ target + 1 and ≥ target − 6 LU (sparse mixes run low), true peak ≤ ceiling
  hero          the hero event (default: the last event with lift ≥ 9 or --hero T) is the loudest
                momentary moment (400 ms, K-weighted) by ≥ 2 LU — the landing beats the move into it
  phone         every event (except "texture": true) stands ≥ 6 dB over the local floor through a
                300 Hz–8 kHz band (phone speakers): low-only sounds vanish there
  collisions    no two event anchors within 40 ms (they smear into one)
  quiet         ≥ 15 % of 100 ms windows sit ≥ 20 LU under the loudest — the mix breathes
  mono          folding to mono loses ≤ 1 dB (pans and reverb don't cancel)
  silences      the declared silences are ≥ 12 LU under the bed level
Warnings (never fail; mgaudio qc thresholds, calibrated on music masters): sub < 60 Hz > 45 % of the energy,
  2–5 kHz > 7.5 % (harsh), < 0.2 % above 5 kHz (dull), < 18 % under 250 Hz (thin), a gap > 0.6 s under -45 LUFS-M.
--png out.png  spectrogram + loudness curve; events white (hero gold), cues.json green, silences blue. Read it.
Exit code 1 if any check fails, so it works in loops.
"""
import json
import warnings
import sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt

warnings.filterwarnings("ignore")

spec_path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mix import resolve_refs  # "cue:…" / "word:…" times → seconds, same as the mixer

spec = resolve_refs(json.loads(spec_path.read_text()), spec_path.parent)
y, sr = sf.read(str(spec_path.parent / spec.get("out", "audio.wav")), always_2d=True)
y = y.T
M = {"lufs": -14.0, "tp": -1.5, **spec.get("master", {})}
meter = pyln.Meter(sr)
fails = []


def lufs(x):
    return meter.integrated_loudness(x.T) if x.shape[1] > int(0.4 * sr) else -70.0


def momentary(x, t, win=0.4):
    a = max(0, int((t - win / 2) * sr))
    seg = x[:, a:a + int(win * sr)]
    return 10 * np.log10(np.mean(np.square(seg)) + 1e-12)  # K-weighting applied to x by the caller


kw = pyln.Meter(sr)
# K-weighted copy of the signal (pyloudnorm's filters) for momentary comparisons
kx = y.copy()
for f in kw._filters.values():
    kx = np.stack([f.apply_filter(ch) for ch in kx])

I = lufs(y)
tp = 20 * np.log10(np.abs(resample_poly(y, 4, 1, axis=1)).max())
print(f"loudness   {I:.1f} LUFS (target {M['lufs']}), true peak {tp:.1f} dBTP (ceiling {M['tp']})")
# Over target = too loud (fail). Under: sparse SFX mixes land 2–6 LU low because the master protects
# the hits instead of flattening them — fine; more than 6 LU low is too quiet for a feed.
if I > M["lufs"] + 1 or I < M["lufs"] - 6:
    fails.append("loudness")
elif I < M["lufs"] - 1.5:
    print(f"           (under target by {M['lufs'] - I:.1f} LU: accepted for a sparse mix; denser sound or more limiting to go louder)")
if tp > M["tp"] + 0.3:
    fails.append("true peak")

ev = sorted(spec.get("events", []), key=lambda e: e["t"])
if len(ev) >= 2:
    heroes = [e for e in ev if e.get("lift", 0) >= 10] or ev
    hero_t = float(sys.argv[sys.argv.index("--hero") + 1]) if "--hero" in sys.argv else heroes[-1]["t"]
    mom = {e["t"]: momentary(kx, e["t"] + 0.1) for e in ev}
    hero = momentary(kx, hero_t + 0.1)
    name = lambda e: e.get("sound") or e["layers"][0]["sound"]
    rival = max((e for e in ev if abs(e["t"] - hero_t) > 0.3), key=lambda e: mom[e["t"]])
    others = mom[rival["t"]]
    print(f"hero       @{hero_t:.2f}: {hero - others:+.1f} LU over the loudest other moment, {name(rival)}@{rival['t']:.2f} (need ≥ +2)")
    if hero - others < 2:
        fails.append("hero")

sos = butter(4, [300, 8000], btype="band", fs=sr, output="sos")
ph = np.stack([sosfilt(sos, ch) for ch in y])
lvl = lambda a, b: 10 * np.log10(np.mean(np.square(ph[:, int(max(0, a) * sr):int(b * sr)])) + 1e-12)
weak = []
for e in ev:
    if e.get("texture"):  # deliberately low (a room tone, a distant tick) — not meant to stand out
        continue
    t = e["t"]
    # a hit is judged on 200 ms around it, a swell/stroke (onset-aligned) on the 600 ms after it starts
    a = lvl(t - 0.05, t + 0.15) if e.get("align", "peak") == "peak" else lvl(t, t + 0.6)
    # against the local floor: the quietest 10 % of 50 ms windows within ±1.5 s (not the neighbour sound)
    win = [lvl(u, u + 0.05) for u in np.arange(max(0, t - 1.5), t + 1.5, 0.05)]
    floor = float(np.percentile(win, 10))
    if a - floor < 6:
        weak.append(f"{(e.get('sound') or e['layers'][0]['sound'])}@{t:.2f} {a - floor:+.0f}")
print("phone      " + ("every event stands ≥ 6 dB over the local floor through 300 Hz–8 kHz" if not weak else "weak on phone speakers: " + ", ".join(weak)))
if weak:
    fails.append("phone")

close = [(a["t"], b["t"]) for a, b in zip(ev, ev[1:]) if b["t"] - a["t"] < 0.04]
print("collisions " + ("none" if not close else ", ".join(f"{a:.2f}/{b:.2f}" for a, b in close)))
if close:
    fails.append("collisions")

hop = int(0.1 * sr)
w = np.array([10 * np.log10(np.mean(np.square(kx[:, i:i + hop])) + 1e-12) for i in range(0, y.shape[1] - hop, hop)])
quiet = float(np.mean(w < w.max() - 20))
print(f"quiet      {quiet:.0%} of 100 ms windows ≥ 20 LU under the peak (need ≥ 15 %)" + (" — narrated: informational" if spec.get("voice") else ""))
if quiet < 0.15 and not spec.get("voice"):  # a voice fills the mix by design
    fails.append("quiet")

mono = y.mean(axis=0, keepdims=True)
loss = lufs(np.vstack([y[0], y[1]])) - lufs(np.vstack([mono[0], mono[0]]))
print(f"mono       fold-down loss {loss:.1f} dB (need ≤ 1)")
if loss > 1:
    fails.append("mono")

for a, b in spec.get("silences", []):
    if b - a >= 0.2 and spec.get("bed"):
        s = 10 * np.log10(np.mean(np.square(kx[:, int((a + 0.08) * sr):int((b - 0.02) * sr)])) + 1e-12)
        print(f"silence    {a:.2f}–{b:.2f}: {s - (spec['bed']['lufs'] + 0.7):+.0f} LU vs the bed")

# ---------- band balance & gaps (mgaudio qc thresholds, calibrated on music masters): warnings, never fails ----------
from scipy.signal import welch
mid = y.mean(axis=0)
fq, P = welch(mid, sr, nperseg=8192)
tot = P[(fq >= 20) & (fq <= 20000)].sum() + 1e-30
BANDS = [("sub", 20, 60), ("bass", 60, 250), ("lowmid", 250, 2000), ("presence", 2000, 5000), ("brilliance", 5000, 12000), ("air", 12000, 20000)]
bands = {n: 100 * P[(fq >= lo) & (fq < hi)].sum() / tot for n, lo, hi in BANDS}
print("balance    " + "  ".join(f"{n} {v:.1f}%" for n, v in bands.items()))
mom_hop = int(0.05 * sr)
mt = np.arange(0, max(1, y.shape[1] - int(0.4 * sr)), mom_hop)
mom = np.array([-0.691 + 10 * np.log10(np.mean(np.square(kx[:, i:i + int(0.4 * sr)])) * 2 + 1e-20) for i in mt])  # ≈ LUFS-M
mtc = mt / sr + 0.2
gap = run = 0.0
for q, tc in zip(mom, mtc):
    run = run + 0.05 if (q < -45 and 0.3 < tc < y.shape[1] / sr - 0.3) else 0.0
    gap = max(gap, run)
warn = []
if bands["sub"] > 45:
    warn.append(f"sub < 60 Hz is {bands['sub']:.0f}% of the energy (> 45 %): boomy, and phones drop it")
if bands["presence"] > 7.5:
    warn.append(f"2–5 kHz is {bands['presence']:.1f}% (> 7.5 %): reads harsh")
if bands["brilliance"] + bands["air"] < 0.2:
    warn.append("almost nothing above 5 kHz: dull")
if bands["sub"] + bands["bass"] < 18:
    warn.append(f"under 250 Hz is {bands['sub'] + bands['bass']:.0f}% (< 18 %): thin" + ("" if spec.get("bed", {}).get("kind") == "music" else " — normal for SFX over an ambience bed"))
if gap > 0.6:
    warn.append(f"a {gap:.2f} s gap under -45 LUFS-M" + (" (no bed: expected for a sparse SFX mix)" if not spec.get("bed") else " — meant? (a declared silence is 0.3–0.5 s)"))
for w_ in warn:
    print(f"  warning: {w_}")
if warn:
    print("  (warnings only: thresholds come from music masters — a sparse SFX/ambience mix can trip them by design)")

if "--png" in sys.argv:  # spectrogram with every event, cue and silence marked — Read the PNG
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.signal import stft
    png = Path(sys.argv[sys.argv.index("--png") + 1])
    dur = y.shape[1] / sr
    f_, t_, Z = stft(mid, sr, nperseg=2048, noverlap=2048 - 256)
    S = 20 * np.log10(np.abs(Z) + 1e-9)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(14, 7.5), sharex=True, gridspec_kw={"height_ratios": [1, 3]})
    tt = np.arange(y.shape[1]) / sr
    step = max(1, y.shape[1] // 6000)
    a1.fill_between(tt[::step], -np.abs(mid[::step]), np.abs(mid[::step]), color="#3b6fd6", lw=0)
    a1.set_ylim(-1, 1)
    a1.set_yticks([])
    a1b = a1.twinx()
    a1b.plot(mtc, mom, color="#e07b2a", lw=1)
    a1b.set_ylim(-60, 0)
    a1b.set_ylabel("LUFS-M")
    a2.pcolormesh(t_, f_, S, shading="auto", cmap="magma", vmin=S.max() - 90, vmax=S.max())
    a2.set_yscale("log")
    a2.set_ylim(30, sr / 2)
    a2.set_yticks([50, 100, 300, 1000, 3000, 8000, 16000], ["50", "100", "300", "1k", "3k", "8k", "16k"])
    for fb in (300, 8000):  # the phone-speaker band
        a2.axhline(fb, color="white", lw=0.6, ls=":", alpha=0.6)
    for a, b in spec.get("silences", []):
        for ax in (a1, a2):
            ax.axvspan(a, b, color="#5ad1ff", alpha=0.18, lw=0)
    cpath = spec_path.parent / spec.get("cues", "cues.json")
    if cpath.exists():
        for i, (k, v) in enumerate(json.loads(cpath.read_text()).items()):
            if isinstance(v, (int, float)) and 0 <= v <= dur:
                a2.axvline(v, color="#9be564", lw=0.8, ls="--", alpha=0.8)
                a2.text(v, 34 * (1.6 ** (i % 3)), k, color="#9be564", fontsize=8, rotation=90, va="bottom",
                        bbox=dict(facecolor="black", alpha=0.6, lw=0, pad=1))
    hero_at = hero_t if len(ev) >= 2 else None
    for i, e in enumerate(ev):
        hero_ev = hero_at is not None and abs(e["t"] - hero_at) < 1e-6
        c = "#ffd23f" if hero_ev else "#ffffff"
        a2.axvline(e["t"], color=c, lw=1.6 if hero_ev else 0.8, alpha=0.9)
        a1.axvline(e["t"], color=c if hero_ev else "#888888", lw=0.8)
        nm = (e.get("sound") or e["layers"][0]["sound"]) + (" (hero)" if hero_ev else "")
        a2.text(e["t"], sr / 2 / (1.7 ** (i % 4)) * 0.9, nm, color=c, fontsize=8, rotation=90, va="top",
                bbox=dict(facecolor="black", alpha=0.6, lw=0, pad=1))
    a2.set_xlim(0, dur)
    a2.set_xlabel("seconds  (white: events, gold: hero, green dashed: cues, blue: silences, dotted: 300 Hz–8 kHz phone band)")
    a1.set_title(f"{spec.get('out', 'audio.wav')}   {I:.1f} LUFS   TP {tp:.1f} dBTP   sub {bands['sub']:.0f}%  bass {bands['bass']:.0f}%  "
                 f"presence {bands['presence']:.1f}%" + ("   FAIL: " + ", ".join(fails) if fails else ""), fontsize=10)
    fig.tight_layout()
    fig.savefig(png, dpi=90)
    print(f"spectrogram → {png}")

print("FAIL: " + ", ".join(fails) if fails else "PASS")
sys.exit(1 if fails else 0)
