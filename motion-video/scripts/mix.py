"""motion-video · mix.py — build the soundtrack from a sound.json, measurably.

    uv run --with librosa --with pedalboard --with pyloudnorm --with soundfile python mix.py sound.json [--video in.mp4 --mux out.mp4]

sound.json (see templates/sound.json):
  duration                 seconds (match the video)
  out                      output WAV path (relative to sound.json)
  master   {lufs:-14, tp:-1.5}
  room     {size:.3, damping:.55, level:.22}         one shared room for every SFX
  assets   {name: {src, license, trim?, hp?, lp?, gain?, start?}}
            src: "kenney:<pack>/<file.ogg>" · "mixkit-sfx:<id>" · "mixkit-music:<id>" · https URL · local path
  events   [{sound | layers:[{sound, gain, offset}], t, align:"peak"|"onset", lift? | gain?, pan, send, pitch?, duck?}]
            align "peak": the loudest sample lands on t (hits); "onset": the first attack lands on t (swells, strokes)
            lift: dB the sound's core sits above the bed right there (needs a bed); gain: fixed dB peak (no bed)
  bed      {asset, kind:"ambience"|"music", lufs (absolute, after the master), offset?, lp?, hp?, fade_in?, fade_out?,
            lift_at?, key_times?}   music: picks the offset where the track lifts at lift_at and key_times hit beats
  silences [[t0, t1], …]   the bed drops out here (score the silence: before the hero hit, at a held breath)

Prints a report: per-event achieved lift, integrated loudness, true peak. Then run qa/verify_audio.py.
Why the rules: references/sound.md.
"""
import io
import json
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import librosa
import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from pedalboard import Compressor, HighpassFilter, LowpassFilter, Pedalboard, PitchShift, Reverb
from scipy.signal import resample_poly

SR = 48000
CACHE = Path.home() / ".cache/motion-video/sound"
KENNEY = {  # CC0 packs (kenney.nl) — the zip URL changes rarely; the page links the current one
    "casino": "https://kenney.nl/media/pages/assets/casino-audio/2472606a04-1721639069/kenney_casino-audio.zip",
    "ui": "https://kenney.nl/media/pages/assets/ui-audio/490d233f68-1677590494/kenney_ui-audio.zip",
    "interface": "https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip",
    "impact": "https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip",
}
meter = pyln.Meter(SR)
db = lambda x: 10 ** (x / 20)
rms = lambda x: float(np.sqrt(np.mean(np.square(x))) + 1e-12)


def kw(x: np.ndarray) -> np.ndarray:
    """K-weighted copy (the LUFS curve) — levels are compared as the ear hears them: a purr that is
    all sub-bass has a big RMS and little loudness; comparing raw RMS made it too quiet."""
    for f in meter._filters.values():
        x = f.apply_filter(x)
    return x


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})) as r:
        return r.read()


def resolve(src: str, base: Path) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    if src.startswith("kenney:"):
        pack, member = src[7:].split("/", 1)
        p = CACHE / f"kenney-{pack}-{Path(member).name}"
        if not p.exists():
            z = zipfile.ZipFile(io.BytesIO(fetch(KENNEY[pack])))
            p.write_bytes(z.read(next(n for n in z.namelist() if n.endswith(member))))
        return p
    for pre, url in (("mixkit-sfx:", "https://assets.mixkit.co/active_storage/sfx/{0}/{0}-preview.mp3"),
                     ("mixkit-music:", "https://assets.mixkit.co/music/{0}/{0}.mp3")):
        if src.startswith(pre):
            i = src[len(pre):]
            p = CACHE / f"{pre[:-1]}-{i}.mp3"
            if not p.exists():
                p.write_bytes(fetch(url.format(i)))
            return p
    if src.startswith("http"):
        p = CACHE / Path(src.split("?")[0]).name
        if not p.exists():
            p.write_bytes(fetch(src))
        return p
    return (base / src).resolve()


def load_asset(a: dict, base: Path) -> np.ndarray:
    y, _ = librosa.load(str(resolve(a["src"], base)), sr=SR, mono=True)
    y = y[int(a.get("start", 0) * SR):]
    chain = []
    if a.get("hp"):
        chain.append(HighpassFilter(a["hp"]))
    if a.get("lp"):
        chain.append(LowpassFilter(a["lp"]))
    if chain:
        y = Pedalboard(chain)(y[None, :].astype(np.float32), SR)[0]
    if a.get("trim"):
        y = y[: int(a["trim"] * SR)].copy()
        n = min(len(y), int(min(0.25, a["trim"] / 3) * SR))
        y[-n:] *= np.linspace(1, 0, n) ** 1.3
    return (y * db(a.get("gain", 0))).astype(np.float32)


def anchor(y: np.ndarray, align: str) -> int:
    if align == "onset":
        on = librosa.onset.onset_detect(y=y, sr=SR, units="samples", backtrack=True)
        return int(on[0]) if len(on) else 0
    return int(np.argmax(np.abs(y)))


def music_offset(y: np.ndarray, dur: float, lift_at: float, key_times: list) -> float:
    """Where to start the track: louder after lift_at than before it, and key moments on beats."""
    sr = 22050
    m = librosa.resample(y, orig_sr=SR, target_sr=sr)
    _, beats = librosa.beat.beat_track(y=m, sr=sr, units="time")
    r = librosa.feature.rms(y=m)[0]
    rt = librosa.times_like(r, sr=sr)
    lvl = lambda a, b: r[(rt >= a) & (rt < b)].mean() if ((rt >= a) & (rt < b)).any() else 1e-6
    best, score = 0.0, -1.0
    for b in beats:
        off = b - lift_at
        if off < 0 or off + dur > len(y) / SR:
            continue
        lift = min(lvl(b, b + 4) / lvl(max(0, b - 4), b), 2.5)
        on_beat = np.mean([np.min(np.abs(beats - (k + off))) < 0.06 for k in key_times]) if key_times else 0
        if lift + 1.2 * on_beat > score:
            best, score = off, lift + 1.2 * on_beat
    return best


def true_peak_limit(x: np.ndarray, ceiling_db: float) -> np.ndarray:
    """Look-ahead limiter on 4× oversampled peaks: transparent unless a hit would cross the ceiling."""
    c = db(ceiling_db)
    up = np.abs(resample_poly(x, 4, 1, axis=1)).max(axis=0)
    peak = up.reshape(-1, 4).max(axis=1)[: x.shape[1]]
    look = int(0.003 * SR)
    need = np.minimum(1.0, c / np.maximum(peak, 1e-9))
    # gain must already be down when the peak arrives: min over a look-ahead window, then smooth release
    from scipy.ndimage import minimum_filter1d
    g = minimum_filter1d(need, size=2 * look + 1, origin=0)
    rel = np.exp(-1 / (0.08 * SR))
    out = np.empty_like(g)
    cur = 1.0
    for i, v in enumerate(g):  # fast attack (already looked ahead), exponential release
        cur = v if v < cur else v + (cur - v) * rel
        out[i] = cur
    return x * out


def tpeak(x: np.ndarray) -> float:
    return 20 * np.log10(np.abs(resample_poly(x, 4, 1, axis=1)).max() + 1e-12)


def master(mix: np.ndarray, lufs: float, tp: float, max_gr: float = 8.0) -> tuple[np.ndarray, float]:
    """Glue, gain toward the target, true-peak limit. The limiter may take at most `max_gr` (8) dB off the
    loudest peak: sparse SFX mixes can't reach -14 LUFS without flattening their hits (the hero first),
    so the transients win and the mix lands a little under target. Returns (audio, gain dB)."""
    mix = Pedalboard([HighpassFilter(28), Compressor(threshold_db=-24, ratio=1.8, attack_ms=15, release_ms=180)])(mix, SR)
    room_db = tp + max_gr - tpeak(mix)  # the most gain the peaks can take
    total = 0.0
    out = mix
    for _ in range(3):
        total = min(total + lufs - meter.integrated_loudness(out.T), room_db)
        out = true_peak_limit(mix * db(total), tp)
    return out, total


def main():
    spec_path = Path(sys.argv[1]).resolve()
    base = spec_path.parent
    spec = json.loads(spec_path.read_text())
    N = int(spec["duration"] * SR)
    assets = {k: load_asset(a, base) for k, a in spec["assets"].items()}
    M = {"lufs": -14.0, "tp": -1.5, **spec.get("master", {})}
    R = {"size": 0.3, "damping": 0.55, "level": 0.22, **spec.get("room", {})}

    # ---------- bed ----------
    bed = np.zeros(N, np.float32)
    bed_ref = bed
    B = spec.get("bed")
    if B:
        y = assets[B["asset"]]
        off = B.get("offset", 0.0)
        if B.get("kind") == "music" and "lift_at" in B:
            off = music_offset(y, spec["duration"], B["lift_at"], B.get("key_times", []))
            print(f"music offset {off:.2f}s")
        y = y[int(off * SR): int(off * SR) + N]
        bed[: len(y)] = y
        fi, fo = int(B.get("fade_in", 0.5) * SR), int(B.get("fade_out", 1.8) * SR)
        bed[:fi] *= np.linspace(0, 1, fi)
        bed[-fo:] *= np.linspace(1, 0, fo) ** 1.3
        bed_ref = bed.copy()  # levels are set against the bed WITHOUT the silences (a hit after a silence must not shrink)
        for a, b in spec.get("silences", []):  # dip to silence with 80 ms fades — the silence is part of the score
            i0, i1, f = int(a * SR), int(b * SR), int(0.08 * SR)
            env = np.ones(N, np.float32)
            env[i0:i1] = 0
            env[max(0, i0 - f):i0] = np.linspace(1, 0, min(f, i0))
            env[i1:i1 + f] = np.linspace(0, 1, len(env[i1:i1 + f]))
            bed *= env
        k0 = db(-30.0 - meter.integrated_loudness(np.stack([bed, bed]).T))  # provisional; fixed after the master
        bed *= k0
        bed_ref = bed_ref * k0
        B.setdefault("lufs", -30.0)

    # ---------- events ----------
    dry, send = np.zeros((2, N), np.float32), np.zeros((2, N), np.float32)
    duck = np.ones(N, np.float32)
    report = []
    for e in spec["events"]:
        layers = e.get("layers") or [{"sound": e["sound"]}]
        main = assets[layers[0]["sound"]]
        y = np.zeros(int(max(len(assets[l["sound"]]) / SR + l.get("offset", 0) for l in layers) * SR) + 1, np.float32)
        for l in layers:  # transient + body + tail: each layer at its own relative gain and offset
            s = assets[l["sound"]] / (np.abs(assets[l["sound"]]).max() + 1e-9) * db(l.get("gain", 0))
            o = int(l.get("offset", 0) * SR)
            y[o:o + len(s)] += s
        if e.get("pitch"):
            y = PitchShift(semitones=e["pitch"])(y[None, :], SR)[0]
        y /= np.abs(y).max() + 1e-9
        k = anchor(y if len(layers) > 1 else main, e.get("align", "peak"))
        c = int(e["t"] * SR)
        hit = e.get("align", "peak") == "peak"
        # The part we level = how loud the sound IS: its loudest 400 ms (momentary loudness), unless it's a
        # click/hit whose energy is a spike (peak > loudest-400 ms + 12 dB) — then 50 ms around the peak.
        # Never "the 400 ms after the onset": a harp sweep starts near-silent and got boosted +16 dB.
        kwy = kw(y)
        win = int(0.4 * SR)
        e2 = np.convolve(np.square(kwy), np.ones(min(win, len(kwy))) / min(win, len(kwy)), mode="valid")
        j0 = int(np.argmax(e2))
        spiky = 20 * np.log10(np.abs(y).max() + 1e-9) - 10 * np.log10(e2[j0] + 1e-12) > 12
        pk = int(np.argmax(np.abs(y)))
        span = (max(0, pk - int(0.025 * SR)), pk + int(0.025 * SR)) if spiky else (j0, j0 + min(win, len(kwy)))
        core = kw(y[span[0]: span[1]])
        if B and "lift" in e:  # adaptive: the core sits `lift` dB (K-weighted) above the bed right where it lands
            around = kw(bed_ref[max(0, c - int(0.3 * SR)): c + int(0.3 * SR)])
            y *= rms(around) * db(e["lift"]) / rms(core) if rms(around) > 1e-6 else db(e.get("gain", -12))
            if os.environ.get("MIX_DEBUG"):
                print(f"  dbg {layers[0]['sound']}@{e['t']:.2f} around {20*np.log10(rms(around)):.1f} core {20*np.log10(rms(core)):.1f} "
                      f"span {(span[1]-span[0])/SR:.2f}s k {k/SR:.2f}s len {len(y)/SR:.2f}s peak {20*np.log10(np.abs(y).max()):.1f}")
        else:
            y *= db(e.get("gain", -12))
        around = kw(bed_ref[max(0, c - int(0.3 * SR)): c + int(0.3 * SR)])
        achieved = 20 * np.log10(rms(kw(y[span[0]: span[1]])) / rms(around)) if B and rms(around) > 1e-6 else None
        if B and e.get("duck", hit):  # the bed steps back 3 dB under a hit: 40 ms in, 300 ms out
            a_, h_, r_ = int(0.04 * SR), int(0.12 * SR), int(0.3 * SR)
            env = np.concatenate([np.linspace(1, db(-3), a_), np.full(h_, db(-3)), np.linspace(db(-3), 1, r_)])
            s0 = c - a_
            sl = slice(max(0, s0), min(N, s0 + len(env)))
            duck[sl] = np.minimum(duck[sl], env[sl.start - s0: sl.stop - s0])
        i0 = c - k
        y = y[max(0, -i0):]
        i0 = max(0, i0)
        y = y[: N - i0]
        ang = (e.get("pan", 0) + 1) * np.pi / 4
        for ch, g in ((0, np.cos(ang)), (1, np.sin(ang))):
            dry[ch, i0:i0 + len(y)] += y * g
            send[ch, i0:i0 + len(y)] += y * g * e.get("send", 0.25)
        report.append((layers[0]["sound"], e["t"], achieved))
    room = Pedalboard([Reverb(room_size=R["size"], damping=R["damping"], wet_level=1.0, dry_level=0.0, width=0.9)])
    sfx = dry + R["level"] * room(send, SR)

    # ---------- master; the bed is held at its absolute level ----------
    # A bed is continuous and hits are short, so the bed dominates integrated loudness: normalising the
    # whole mix to -14 would drag the bed up to ~-18. So the bed keeps its absolute target (bed.lufs) and
    # the master's gain lands on the SFX: `lift` sets the BALANCE between events; every event ends up
    # `lift + Δ` over the bed, Δ reported below.
    delta = 0.0
    if B:
        for _ in range(3):
            st = np.stack([bed * duck, bed * duck])
            _, G = master(sfx + st, M["lufs"], M["tp"])
            step = B["lufs"] - (meter.integrated_loudness(np.stack([bed, bed]).T) + G)
            bed *= db(step)
            delta -= step
    st = np.stack([bed * duck, bed * duck]) if B else 0
    out, G = master(sfx + st, M["lufs"], M["tp"])
    path = base / spec.get("out", "audio.wav")
    sf.write(str(path), out.T, SR, subtype="PCM_24")

    tp = tpeak(out)
    I = meter.integrated_loudness(out.T)
    if I < M["lufs"] - 1:
        print(f"  note: {I:.1f} LUFS < target — the limiter was capped at 8 dB to keep the hits; louder needs denser sound")
    print(f"→ {path.name}: {meter.integrated_loudness(out.T):.1f} LUFS, true peak {tp:.1f} dBTP"
          + (f", bed {meter.integrated_loudness(np.stack([bed, bed]).T) + G:.1f} LUFS" if B else ""))
    if B:
        print(f"  Δ = {delta:+.1f} dB: every event sits lift + Δ over the bed")
        print("  lift (balance): " + "  ".join(f"{n}@{t:.2f} {d:+.0f}" for n, t, d in report if d is not None))

    if "--mux" in sys.argv:
        src = sys.argv[sys.argv.index("--video") + 1]
        dst = sys.argv[sys.argv.index("--mux") + 1]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-i", str(path), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", dst], check=True)
        print(f"→ {dst}")


if __name__ == "__main__":
    main()
