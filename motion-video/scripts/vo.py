"""motion-video · vo.py — the voice as the clock: tidy a narration, time every word, cut captions, check it.

    U="uv run --with numpy --with soundfile python"
    $U vo.py tidy  s1.wav [s2.wav …] -o vo.wav [--lead 0.5] [--gap 0.28] [--breath 0.45] [--pause 3:2.0]
    $U vo.py words vo.wav script.txt [--lang auto] [--model ggml.bin] [--max 42]       # → words.json, captions.json
    $U vo.py all   s1.wav [s2.wav …] --script script.txt -o vo.wav                    # tidy + words
    $U vo.py check final.mp4 script.txt [--max-wer 0.02]                              # STT check before delivery

Any voice works: a TTS export (any vendor) or a human recording, one file for the whole script or one per
section. The script is plain text; a blank line separates sections (one per input file), `#` lines are notes.

tidy   decode (any format ffmpeg reads; --tempo 1.05 speeds up without pitch change), trim the silence at
       both ends, squeeze inner pauses: a pause ≥ --sentence (0.6 s) becomes a breath (--breath 0.45 s), a
       shorter one over --gap (0.28 s) becomes --gap (TTS stops ~0.6 s at every full stop; 0.28 s reads as one
       speaker talking). Sections join with --section (0.45 s); `--pause i:s` holds s seconds before section i
       where the picture carries on alone. --lead (0.5 s) before the first word, --tail (0.5 s) after.
       Writes 48 kHz mono 24-bit, and merges section starts into cues.json ("s1", "s2", …, "vo_end").
words  word times by ASR — whisper.cpp (`whisper-cli`, DTW timestamps) if on PATH, else faster-whisper or
       openai-whisper through uv — then aligned to the SCRIPT's words: the script's spelling is kept (ASR
       mishears brand names), the ASR's times are used. ASR times are calibrated on the audio itself: words
       right after a pause must start where the voice starts; the median miss is the engine's bias, removed
       from every word; then starts snap out of silences and ends stop at the next pause.
       → words.json [{w, t0, t1}] (w as written in the script, punctuation kept; "miss": true = not heard,
         time interpolated) and captions.json [{text, t0, t1, words: [i0, i1]}]: ≤ --max chars, broken at
         punctuation and pauses, never across a sentence, no flicker gaps < 0.3 s, ≥ 0.7 s each.
check  ASR on the final mix (music and all) against the script: word error rate + every mismatch with its
       time. Number spellings ("20" / "twenty") and anything heard before/after the narration (music) are
       listed but not counted. Exit 1 if WER > --max-wer.

Model: --model or $WHISPER_MODEL, default ~/.cache/whisper-cpp/ggml-large-v3-turbo.bin (whisper-cli);
faster-whisper uses $FW_MODEL (default "small"). --engine forces one. Why: references/voice.md.
"""
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

import numpy as np

SR = 48000
HOP = 0.01  # envelope frame, s
DEFAULT_MODEL = "~/.cache/whisper-cpp/ggml-large-v3-turbo.bin"
DTW_PRESETS = {"tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "medium.en",
               "large.v1", "large.v2", "large.v3", "large.v3.turbo"}


# ── audio ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def decode(path, sr=SR, tempo=1.0):
    af = ["-af", f"atempo={tempo}"] if abs(tempo - 1) > 1e-3 else []
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), *af, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def env_db(x, sr=SR):
    h = int(HOP * sr)
    n = len(x) // h
    return 10 * np.log10(np.mean(np.square(x[: n * h].reshape(n, h)), axis=1) + 1e-12)


def voiced(x, thresh=None, sr=SR):
    """Frames (10 ms) that carry voice. Adaptive threshold: 38 dB under the speech level (95th pct), but at least
    8 dB over the noise floor (10th pct) — works for clean TTS and for a room recording. Quiet consonant tails are
    protected by a 30 ms hangover (20 ms before an onset)."""
    d = env_db(x, sr)
    thr = thresh if thresh is not None else max(np.percentile(d, 10) + 8, np.percentile(d, 95) - 38)
    v = d > thr
    out = v.copy()
    for k in (1, 2, 3):
        out[:-k] |= v[k:] if k <= 2 else False  # pre-roll 20 ms
        out[k:] |= v[:-k]                        # hangover 30 ms
    return out, thr


def runs(mask):
    """[(start, end, value)] in frames."""
    if not len(mask):
        return []
    edges = np.flatnonzero(np.diff(mask.astype(np.int8))) + 1
    b = np.concatenate([[0], edges, [len(mask)]])
    return [(int(a), int(c), bool(mask[a])) for a, c in zip(b[:-1], b[1:])]


def pauses(x, min_len=0.12, thresh=None):
    """Silent stretches inside the speech: [(t0, t1)] in seconds, plus (first voice, last voice)."""
    v, _ = voiced(x, thresh)
    rs = runs(v)
    on = [r for r in rs if r[2]]
    if not on:
        return [], (0.0, len(x) / SR)
    first, last = on[0][0] * HOP, on[-1][1] * HOP
    ps = [(a * HOP, b * HOP) for a, b, val in rs if not val and a > on[0][0] and b < on[-1][1] and (b - a) * HOP >= min_len]
    return ps, (first, last)


def write_wav(path, x):
    import soundfile as sf
    sf.write(str(path), x.astype(np.float32), SR, subtype="PCM_24")


# ── tidy ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def tidy_one(x, a):
    v, thr = voiced(x, a.thresh)
    rs = runs(v)
    on = [r for r in rs if r[2]]
    if not on:
        sys.exit("tidy: no voice found (try --thresh)")
    h = int(HOP * SR)
    i0, i1 = on[0][0] * h, min(len(x), on[-1][1] * h + int(0.05 * SR))
    parts, squeezed, fade = [], 0, int(0.01 * SR)
    for s, e, val in rs:
        s, e = max(s * h, i0), min(e * h, i1)
        if e <= s:
            continue
        chunk = x[s:e]
        L = (e - s) / SR
        if not val and s > i0 and e < i1:
            keep = a.breath if L >= a.sentence else a.gap if L > a.gap else None
            if keep is not None and L > keep + 0.02:
                k = int(keep * SR / 2)
                head, tail = chunk[:k].copy(), chunk[-k:].copy()
                head[-fade:] *= np.linspace(1, 0, fade)  # the room tone of a real recording must not click
                tail[:fade] *= np.linspace(0, 1, fade)
                chunk = np.concatenate([head, tail])
                squeezed += 1
        parts.append(chunk)
    y = np.concatenate(parts)
    n = int(0.005 * SR)
    y[:n] *= np.linspace(0, 1, n)
    y[-n:] *= np.linspace(1, 0, n)
    return y, squeezed, thr


def cmd_tidy(a):
    holds = {int(k): float(s) for k, s in (p.split(":") for p in a.pause)}
    out, t, cues, rows = [np.zeros(int(a.lead * SR), np.float32)], a.lead, {}, []
    for i, src in enumerate(a.inputs, 1):
        x = decode(src, tempo=a.tempo)
        y, sq, thr = tidy_one(x, a)
        if i > 1:
            g = holds.get(i, a.section)
            out.append(np.zeros(int(g * SR), np.float32))
            t += g
        cues[f"s{i}"] = round(t, 3)
        rows.append(f"  s{i} {t:6.2f}–{t + len(y) / SR:6.2f}  {Path(src).name}: {len(x) / SR:.2f} → {len(y) / SR:.2f} s, "
                    f"{sq} pauses squeezed (gate {thr:.0f} dBFS)")
        out.append(y)
        t += len(y) / SR
    cues["vo_end"] = round(t, 3)
    out.append(np.zeros(int(a.tail * SR), np.float32))
    y = np.concatenate(out)
    write_wav(a.out, y)
    print(f"→ {a.out}: {len(y) / SR:.2f} s (voice {a.lead:.2f}–{t:.2f} s)")
    print("\n".join(rows))
    if not a.no_cues:
        cp = Path(a.cues) if a.cues else Path(a.out).parent / "cues.json"
        old = json.loads(cp.read_text()) if cp.exists() else {}
        old.update(cues)
        cp.write_text(json.dumps(old, indent=1, ensure_ascii=False))
        print(f"→ {cp}: " + ", ".join(f"{k} {v:.2f}" for k, v in cues.items()))


# ── ASR ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
FW_CODE = r"""
import json, sys
from faster_whisper import WhisperModel
path, lang, model = sys.argv[1:4]
m = WhisperModel(model, device="cpu", compute_type="int8")
segs, _ = m.transcribe(path, language=None if lang == "auto" else lang, word_timestamps=True)
print("@@" + json.dumps([[w.word.strip(), w.start, w.end] for s in segs for w in s.words]))
"""
OW_CODE = r"""
import json, sys, whisper
path, lang, model = sys.argv[1:4]
r = whisper.load_model(model).transcribe(path, language=None if lang == "auto" else lang, word_timestamps=True)
print("@@" + json.dumps([[w["word"].strip(), w["start"], w["end"]] for s in r["segments"] for w in s["words"]]))
"""


def asr(path, a):
    """→ [(word, t0, t1|None)] in seconds, file time."""
    model = Path(os.path.expanduser(a.model or os.environ.get("WHISPER_MODEL") or DEFAULT_MODEL))
    engine = a.engine
    if engine == "auto":
        engine = "whisper-cli" if shutil.which("whisper-cli") and model.exists() else "faster-whisper"
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "16000", str(wav)], check=True)
        if engine == "whisper-cli":
            preset = re.sub(r"-q\d.*$", "", model.stem.removeprefix("ggml-")).replace("-", ".")
            dtw = ["-dtw", preset, "-nfa"] if preset in DTW_PRESETS else []  # DTW needs flash attention off
            subprocess.run(["whisper-cli", "-m", str(model), "-f", str(wav), "-l", a.lang, "-ojf", "-of", f"{td}/r", "-np",
                            *dtw], check=True, capture_output=True)
            # tokens can split a multi-byte character (Cyrillic, CJK): keep raw bytes until the word is whole
            return cli_words(json.loads(Path(f"{td}/r.json").read_bytes().decode("utf-8", "surrogateescape")))
        code = FW_CODE if engine == "faster-whisper" else OW_CODE
        pkg = "faster-whisper" if engine == "faster-whisper" else "openai-whisper"
        name = os.environ.get("FW_MODEL", "small")
        r = subprocess.run(["uv", "run", "-q", "--with", pkg, "python", "-c", code, str(wav), a.lang, name],
                           capture_output=True, text=True)
        line = next((l for l in r.stdout.splitlines() if l.startswith("@@")), None)
        if not line:
            sys.exit(f"{engine} failed:\n{r.stderr[-2000:]}")
        return [(w, s, e) for w, s, e in json.loads(line[2:])]


def cli_words(j):
    """whisper.cpp tokens → words: a token starting with a space starts a word; punctuation sticks to the word
    before; special tokens ([_BEG_], [_TT_…]) are skipped. Time = DTW time if present, else the token offset."""
    out = []
    for seg in j["transcription"]:
        for tk in seg.get("tokens", []):
            s = tk["text"]
            if s.startswith("[_") or not s.strip():
                continue
            t = tk["t_dtw"] / 100 if tk.get("t_dtw", -1) >= 0 else tk["offsets"]["from"] / 1000
            if out and (not s.startswith(" ") or not norm(s)):  # a word piece ("ora") or punctuation
                out[-1][0] += s.strip() if not norm(s) else s
                continue
            out.append([s.strip(), t, None])
    fix = lambda w: w.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
    return [(fix(w), t, e) for w, t, e in out if norm(fix(w))]


# ── text ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
def norm(w):
    w = unicodedata.normalize("NFKC", w).lower().replace("ё", "е")
    return "".join(c for c in w if c.isalnum())


def read_script(p):
    """→ [(word as written, section index)]; standalone punctuation (— …) sticks to the word before."""
    secs = re.split(r"\n\s*\n", "\n".join(l for l in Path(p).read_text(encoding="utf-8").splitlines()
                                          if not l.lstrip().startswith("#")))
    out = []
    for si, s in enumerate((s for s in secs if s.strip()), 1):
        for w in s.split():
            if not norm(w) and out:
                out[-1] = (out[-1][0] + " " + w, out[-1][1])
            elif norm(w):
                out.append((w, si))
    return out


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def calibrate(hw, x):
    """Shift ASR times by the engine's bias (measured on words that start right after a pause), snap those words
    onto the voice onset, move starts out of silences, end every word at the next word or the next pause."""
    ps, (first, last) = pauses(x)
    starts = [first] + [b for _, b in ps]
    t = np.array([w[1] for w in hw])
    if not len(t):
        return hw
    # words that open a sentence or clause (by the ASR's own punctuation) are the ones that follow a pause:
    # each should start on a voice onset. Their median miss is the engine's bias (whisper.cpp DTW runs ~0.25 s
    # late). Clause starts are a second apart, so the pairing can't slip by one word the way all words can.
    cand = [i for i in range(len(hw)) if i == 0 or re.search(r"[.!?,;:…]$", hw[i - 1][0])]
    cand = cand if len(cand) >= 2 else list(range(len(hw)))
    bias = 0.0
    for win in (0.45, 0.3):
        miss = [t[i] - bias - s for i in cand for s in [min(starts, key=lambda s: abs(t[i] - bias - s))]
                if abs(t[i] - bias - s) < win]
        if len(miss) >= 2:
            bias += float(np.median(miss))
    t = t - bias
    pairs = []
    for s in starts:  # the word nearest each onset starts exactly there
        j = int(np.argmin(np.abs(t - s)))
        if abs(t[j] - s) < 0.3:
            pairs.append((j, s))
            t[j] = s
    for a, b in ps:  # a start inside a pause belongs to the voice after it
        t[(t > a) & (t < b)] = b
    t = np.maximum.accumulate(np.clip(t, first, last))
    ends = []
    for i in range(len(t)):
        nxt = t[i + 1] if i + 1 < len(t) else last
        stop = next((a for a, b in ps if t[i] < a <= nxt), nxt)
        ends.append(max(stop, t[i] + 0.04))
    print(f"  calibration: engine bias {bias:+.3f} s from {len(pairs)} post-pause words, {len(ps)} pauses")
    return [(w[0], float(t[i]), float(ends[i])) for i, w in enumerate(hw)]


def align(script, heard):
    """Script words get ASR times: matching words 1:1, a replaced run (mishearing, "20" vs "twenty") shares its
    span by length, a word the ASR missed is interpolated between its neighbours ("miss")."""
    A, B = [norm(w) for w, _ in script], [norm(w) for w, _, _ in heard]
    T = [None] * len(script)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                T[i1 + k] = heard[j1 + k][1:]
        elif op == "replace":
            t0, t1 = heard[j1][1], heard[j2 - 1][2]
            L = np.cumsum([0] + [max(1, len(A[i])) for i in range(i1, i2)])
            for k in range(i2 - i1):
                T[i1 + k] = (t0 + (t1 - t0) * L[k] / L[-1], t0 + (t1 - t0) * L[k + 1] / L[-1])
    out, miss = [], 0
    for i, (w, _) in enumerate(script):
        if T[i] is None:  # not heard: share the gap between the known neighbours
            miss += 1
            p = T[i - 1][1] if i else (heard[0][1] if heard else 0.0)
            j = next((k for k in range(i + 1, len(script)) if T[k]), None)
            n = (j if j is not None else len(script)) - i
            q = T[j][0] if j is not None else p + 0.3 * n
            span = (q - p) / max(1, n)
            T[i] = [p, p + span]  # list = interpolated
        out.append({"w": w, "t0": round(float(T[i][0]), 3), "t1": round(float(T[i][1]), 3)} | ({"miss": True} if isinstance(T[i], list) else {}))
    return out, miss


def captions(words, script, mx):
    """Phrases end at punctuation or a pause ≥ 0.25 s; phrases merge while they fit in mx and no sentence ends
    between them; an over-long phrase splits into balanced pieces at word boundaries."""
    n = len(words)
    sec = [s for _, s in script]
    phrases, cur = [], []
    for i in range(n):
        cur.append(i)
        last = i == n - 1
        gap = 0 if last else words[i + 1]["t0"] - words[i]["t1"]
        w = words[i]["w"].rstrip("\"'»”)")
        hard = last or sec[i] != sec[i + 1] or bool(re.search(r"[.!?…]$", w)) or gap >= 0.4
        if hard or re.search(r"[,;:—–]$", w) or gap >= 0.25:
            phrases.append((cur, hard))
            cur = []
    text = lambda ix: " ".join(words[i]["w"] for i in ix)
    pieces = []
    for ix, hard in phrases:  # split long phrases
        if len(text(ix)) <= mx:
            pieces.append((ix, hard))
            continue
        k = -(-len(text(ix)) // mx)
        while True:
            target, chunk, split = len(text(ix)) / k, [], []
            for i in ix:
                over = len(text(chunk + [i])) > mx
                closer = len(split) < k - 1 and abs(len(text(chunk + [i])) - target) > abs(len(text(chunk)) - target)
                if chunk and (over or closer):
                    split.append(chunk)
                    chunk = []
                chunk.append(i)
            split.append(chunk)
            if all(len(text(c)) <= mx for c in split) or k > len(ix):
                break
            k += 1
        pieces += [(c, hard and c is split[-1]) for c in split]
    merged = []
    for ix, hard in pieces:
        if merged and not merged[-1][1] and len(text(merged[-1][0] + ix)) <= mx:
            merged[-1] = (merged[-1][0] + ix, hard)
        else:
            merged.append((ix, hard))
    out = []
    for k, (ix, _) in enumerate(merged):
        t0 = max(words[ix[0]]["t0"] - 0.05, out[-1]["t1"] if out else 0)
        nxt = words[merged[k + 1][0][0]]["t0"] - 0.05 if k + 1 < len(merged) else None
        t1 = words[ix[-1]]["t1"] + 0.15
        t1 = max(t1, t0 + 0.7)
        if nxt is not None and (nxt - t1 < 0.3 or t1 > nxt):
            t1 = nxt
        out.append({"text": text(ix), "t0": round(t0, 3), "t1": round(t1, 3), "words": [ix[0], ix[-1]]})
    return out


def cmd_words(a, audio=None):
    audio = audio or a.audio
    script = read_script(a.script)
    x = decode(audio)
    heard = asr(audio, a)
    print(f"  ASR heard {len(heard)} words, the script has {len(script)}")
    heard = calibrate(heard, x)
    words, miss = align(script, heard)
    caps = captions(words, script, a.max)
    d = Path(a.out_dir or Path(audio).parent)
    (d / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=0))
    (d / "captions.json").write_text(json.dumps(caps, ensure_ascii=False, indent=1))
    print(f"→ {d / 'words.json'}: {len(words)} words" + (f", {miss} not heard (interpolated, \"miss\": true)" if miss else ""))
    fast = [c for c in caps if len(c["text"]) / max(0.01, c["t1"] - c["t0"]) > 17]
    print(f"→ {d / 'captions.json'}: {len(caps)} captions ≤ {a.max} chars" + (f"; {len(fast)} over 17 chars/s" if fast else ""))
    for c in caps:
        print(f"  {c['t0']:6.2f} {c['t1']:6.2f}  {c['text']}")
    if miss > 0.2 * len(script):
        print("  ! many words not heard: wrong script, wrong --lang, or a very noisy file", file=sys.stderr)


def cmd_all(a):
    cmd_tidy(a)
    if not a.out_dir:
        a.out_dir = str(Path(a.out).parent)
    cmd_words(a, a.out)


# ── check ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def cmd_check(a):
    script = [w for w, _ in read_script(a.script)]
    heard = asr(a.audio, a)
    A, B = [norm(w) for w in script], [norm(w) for w, _, _ in heard]
    errs, soft, extra = 0, [], []
    lines = []
    isnum = lambda ws: any(any(c.isdigit() for c in w) for w in ws)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        said = " ".join(w for w, _, _ in heard[j1:j2])
        want = " ".join(script[i1:i2])
        t = heard[j1][1] if j1 < len(heard) else (heard[-1][1] if heard else 0)
        if op == "insert" and (i1 == 0 or i1 == len(A)):
            extra.append(f"@{t:.2f} \"{said}\"")
        elif op == "replace" and (isnum(A[i1:i2]) or isnum(B[j1:j2])):
            soft.append(f"@{t:.2f} script \"{want}\" ~ heard \"{said}\"")
        else:
            errs += max(i2 - i1, j2 - j1)
            lines.append(f"@{t:6.2f}  {op:7}  script \"{want}\"  →  heard \"{said}\"")
    wer = errs / max(1, len(A))
    print(f"STT check: {len(A)} script words, {len(B)} heard, WER {wer:.1%} ({errs} errors)")
    for l in lines:
        print("  " + l)
    if soft:
        print("  numbers (spelling differs — check by ear): " + "; ".join(soft))
    if extra:
        print("  heard outside the narration (music? not counted): " + "; ".join(extra))
    print("PASS" if wer <= a.max_wer else f"FAIL: WER over {a.max_wer:.0%}")
    sys.exit(0 if wer <= a.max_wer else 1)


# ── cli ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def tidy_args(p):
        p.add_argument("-o", "--out", default="vo.wav")
        p.add_argument("--lead", type=float, default=0.5, help="silence before the first word")
        p.add_argument("--tail", type=float, default=0.5, help="silence after the last word")
        p.add_argument("--gap", type=float, default=0.28, help="inner pauses longer than this shrink to it")
        p.add_argument("--breath", type=float, default=0.45, help="what a sentence pause becomes")
        p.add_argument("--sentence", type=float, default=0.6, help="a raw pause this long counts as a sentence end")
        p.add_argument("--section", type=float, default=0.45, help="gap between section files")
        p.add_argument("--pause", nargs="*", default=[], help="i:s — hold s seconds before section i")
        p.add_argument("--tempo", type=float, default=1.0, help="speed up/down without pitch change (0.5–2)")
        p.add_argument("--thresh", type=float, help="voice gate in dBFS (default: adaptive)")
        p.add_argument("--cues", help="cues.json to merge section starts into (default: next to --out)")
        p.add_argument("--no-cues", action="store_true")

    def asr_args(p):
        p.add_argument("--lang", default="auto")
        p.add_argument("--model", help=f"whisper.cpp ggml model (default $WHISPER_MODEL or {DEFAULT_MODEL})")
        p.add_argument("--engine", default="auto", choices=["auto", "whisper-cli", "faster-whisper", "whisper"])

    p = sp.add_parser("tidy")
    p.add_argument("inputs", nargs="+")
    tidy_args(p)
    p.set_defaults(f=cmd_tidy)
    for name in ("words", "all"):
        p = sp.add_parser(name)
        if name == "words":
            p.add_argument("audio")
            p.add_argument("script")
        else:
            p.add_argument("inputs", nargs="+")
            p.add_argument("--script", required=True)
            tidy_args(p)
        asr_args(p)
        p.add_argument("--max", type=int, default=42, help="caption chunk length, characters")
        p.add_argument("--out-dir", help="where words.json / captions.json go (default: next to the audio)")
        p.set_defaults(f=cmd_words if name == "words" else cmd_all)
    p = sp.add_parser("check")
    p.add_argument("audio")
    p.add_argument("script")
    asr_args(p)
    p.add_argument("--max-wer", type=float, default=0.02)
    p.set_defaults(f=cmd_check)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
