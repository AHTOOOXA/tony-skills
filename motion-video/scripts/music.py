"""motion-video · music.py — a generated, licence-free music bed fitted to the film's cues.

    uv run --with numpy --with scipy --with numba --with pedalboard --with soundfile --with pyloudnorm \
        python music.py lofi --len 15 --drop cue:hero --outro cue:logo -o bed.wav
    … music.py list                                                   # recipes, defaults, extras
    … music.py ambient --len 12 --hits cue:a,cue:b,cue:c --set flavor=piano -o bed.wav
    … music.py --style 02-line-art --len 10 -o bed.wav                 # mg-styles' pick for that look
    … --with matplotlib … --png bed.png                               # + mgaudio's spectrogram with the sections

A thin wrapper around mgaudio (lib/audio of github.com/Vincentwei1021/mg-styles-15, MIT; its samples are VCSL,
CC0). The first run downloads that folder (~60 MB, pinned commit) to ~/.cache/motion-video/mgaudio/.
The recipe arranges intro → build → drop → outro on a tempo grid whose bar 0 sits exactly on --drop;
--outro is where the final chord starts (the end card); with --hits (≥ 2 times) and no --bpm the tempo is
fitted so the hits sit on its 8th-note grid (mgaudio's fit_bpm; the report prints the worst error).
Times: seconds, or "cue:name", "cue:name+0.1" from cues.json (--cues, default ./cues.json).
--set k=v passes recipe extras (flavor=piano, keys=rhodes, vinyl=false, gap=true …); numbers/bools parsed.

Writes the WAV (48 kHz, 24-bit, mastered to -14 LUFS — mix.py re-levels it to bed.lufs anyway) and a sidecar
<out>.json: recipe, kwargs, bpm, fit error, sections, beats/downbeats in film time, licence.
Use it in sound.json as {"bed": {"asset": "music", "kind": "music", "offset": 0, "lufs": -20}} with
"music": {"src": "bed.wav", "license": "generated (mgaudio MIT, VCSL CC0)"}.

Nobody has judged these beds by ear: render one next to a stock track and let a human choose (sound.md §1).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = "Vincentwei1021/mg-styles-15"
REF = os.environ.get("MGAUDIO_REF", "49052d80bfaf9fa8412cc9710530e5e95a3b8d8c")  # pinned: 2026-10-05 HEAD
ROOT = Path.home() / ".cache/motion-video/mgaudio" / REF[:12]
LIB = ROOT / "lib/audio"


def fetch(url: str) -> bytes:
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "motion-video"}), timeout=120) as r:
                return r.read()
        except Exception:
            if i == 2:
                raise
            time.sleep(2 * (i + 1))


def ensure_lib() -> Path:
    """Download lib/audio (code + bundled CC0 samples) + LICENSE at the pinned commit, once."""
    if (LIB / ".complete").exists():
        return LIB
    tree = json.loads(fetch(f"https://api.github.com/repos/{REPO}/git/trees/{REF}?recursive=1"))["tree"]
    want = [x["path"] for x in tree if x["type"] == "blob" and (x["path"].startswith("lib/audio/") or x["path"] == "LICENSE")]
    print(f"music: fetching mgaudio ({len(want)} files, ~60 MB) → {ROOT}", file=sys.stderr)

    def get(p):
        dst = ROOT / p
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(dst.suffix + ".part")
            tmp.write_bytes(fetch(f"https://raw.githubusercontent.com/{REPO}/{REF}/{urllib.parse.quote(p)}"))
            tmp.rename(dst)

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(get, want))
    # index.json lists the full VCSL selection, but the repo ships only part of it (piano 39/73 files, no shaker,
    # triangle, gong, guzheng …): a missing file crashes the render. Keep the full index aside and list only what
    # is on disk — instruments with nothing left fall back to mgaudio's synth versions (its own `available()` rule).
    idx = LIB / "samples/index.json"
    keep = idx.with_name("index.full.json")
    if not keep.exists():
        keep.write_text(idx.read_text())
    full = json.loads(keep.read_text())
    idx.write_text(json.dumps({k: [x for x in v if (idx.parent / x["file"]).exists()] for k, v in full.items()}))
    (ROOT / "SOURCE.txt").write_text(f"https://github.com/{REPO} @ {REF}\nCode: MIT (LICENSE). lib/audio/samples: VCSL, CC0.\n")
    (LIB / ".complete").write_text(REF)
    return LIB


def parse_val(v: str):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lower() == "none":
        return None
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def main():
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    sys.path.insert(0, str(ensure_lib()))
    import inspect
    import numpy as np
    from mgaudio import recipes

    if not a or a[0] in ("list", "-h", "--help"):
        print("recipe        defaults (signature)                      styles that use it (mg-styles slug)")
        by = {}
        for slug, (name, kw, alt, _) in recipes.STYLES.items():
            by.setdefault(name, []).append(slug + (f" {kw}" if kw else ""))
        for name, fn in recipes.RECIPES.items():
            sig = inspect.signature(fn)
            extras = [f"{k}={p.default!r}" for k, p in sig.parameters.items()
                      if k in ("bpm", "key", "mode", "prog", "flavor", "keys", "vinyl", "lead", "gap", "slow", "tape_stop",
                               "accent_hits", "pattern", "dizi")]
            print(f"{name:13s} {', '.join(extras)}\n{'':13s} used for: {'; '.join(by.get(name, ['—']))}")
        print("\nflags: --len S  --drop T  --outro T  --build T  --hits T,T,…  --bpm N  --key F  --mode minor"
              "  --prog 'ii9 V13 Imaj9'  --set k=v  --cues cues.json  --style <slug>  --png spec.png  -o bed.wav")
        return

    cues_path = Path(opt("--cues", "cues.json"))
    cues = json.loads(cues_path.read_text()) if cues_path.exists() else {}

    def t_of(s):
        s = str(s).strip()
        m = re.match(r"^cue:(.+?)\s*([+-]\s*\d+(?:\.\d+)?)?$", s)
        if not m:
            return float(s)
        name = s[4:] if s[4:] in cues else m.group(1)
        if name not in cues:
            sys.exit(f"music: unknown cue \"{name}\" — {cues_path} has: {', '.join(cues) or 'nothing'}")
        return float(cues[name]) + (float(m.group(2).replace(" ", "")) if m.group(2) and name != s[4:] else 0.0)

    if "--len" not in a:
        sys.exit("music: --len <seconds> (the film's length) is required")
    kw = {"duration": float(opt("--len"))}
    for flag, key in (("--drop", "drop"), ("--outro", "outro"), ("--build", "build")):
        if flag in a:
            kw[key] = t_of(opt(flag))
    if "--hits" in a:
        kw["hits"] = [t_of(x) for x in opt("--hits").split(",") if x.strip()]
    if "--bpm" in a:
        kw["bpm"] = float(opt("--bpm"))
    for flag in ("--key", "--mode", "--prog"):
        if flag in a:
            kw[flag[2:]] = opt(flag)
    for i, x in enumerate(a):
        if x == "--set":
            k, v = a[i + 1].split("=", 1)
            kw[k] = parse_val(v)

    if "--style" in a:
        slug = opt("--style")
        name = next((recipes.STYLES[s][0] for s in recipes.STYLES if s == slug or s.split("-", 1)[1] == slug), None)
        if not name:
            sys.exit(f"music: unknown style {slug!r}; one of {', '.join(recipes.STYLES)}")
        m = recipes.for_style(slug, **kw)
    else:
        name = a[0]
        if name not in recipes.RECIPES:
            sys.exit(f"music: unknown recipe {name!r}; one of {', '.join(recipes.RECIPES)} (music.py list)")
        m = recipes.RECIPES[name](**kw)

    out = Path(opt("-o", f"{name}.wav")).resolve()
    png = opt("--png")
    f = m.form
    res = m.export(str(out), lufs=-14, tp=-1, spectrogram=png)
    beats = [round(float(t), 3) for t in np.arange(f.drop - 64 * f.beat, f.duration, f.beat) if 0 <= t < f.duration]
    bars = [round(float(t), 3) for t in np.arange(f.drop - 16 * f.bar, f.duration, f.bar) if 0 <= t < f.duration]
    side = {
        "recipe": name, "kwargs": {k: v for k, v in kw.items()}, "bpm": round(f.bpm, 2),
        "fit_err": None if f.fit_err is None else round(float(f.fit_err), 4),
        "sections": {"intro": 0.0, "build": round(f.build, 3), "drop": round(f.drop, 3), "outro": round(f.outro, 3), "end": round(f.duration, 3)},
        "beats": beats, "downbeats": bars,
        "lufs": round(float(res.get("lufs", 0)), 2) if isinstance(res, dict) else None,
        "warnings": res.get("warnings", []) if isinstance(res, dict) else [],
        "license": f"generated with mgaudio (github.com/{REPO} @ {REF[:12]}, MIT); samples VCSL (CC0)",
    }
    out.with_suffix(".json").write_text(json.dumps(side, indent=1).replace("\n  ", " ").replace("\n ]", " ]"))
    print(f"→ {out.name}: {name}, {f.bpm:.1f} BPM" + (f" (fitted to {len(kw['hits'])} hits, worst error {f.fit_err * 1000:.0f} ms)" if f.fit_err is not None else "")
          + f", build {f.build:.2f} · drop {f.drop:.2f} · outro {f.outro:.2f} · end {f.duration:.2f} s")
    if side["warnings"]:
        print("  mgaudio qc: " + "; ".join(map(str, side["warnings"])))
    if png:
        print(f"  spectrogram → {png}")
    print(f"  sidecar → {out.with_suffix('.json').name} (beats/downbeats in film time). Judge it BY EAR next to a stock track.")


if __name__ == "__main__":
    main()
