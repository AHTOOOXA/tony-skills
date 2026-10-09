"""motion-video · find_sound.py — find stock sounds by name: Mixkit SFX, Mixkit music, VCSL instruments.

    python3 find_sound.py sfx                                  # list Mixkit SFX tags
    python3 find_sound.py sfx whoosh paper [--grep air]       # cards on those tag pages → mixkit-sfx:<id>
    python3 find_sound.py music                                # list music genres / moods / instruments
    python3 find_sound.py music cinematic mood/relaxed [--grep piano] [--pages 3] [--max-len 150]
    python3 find_sound.py vcsl                                 # VCSL aliases (CC0 recorded instruments)
    python3 find_sound.py vcsl glock [loud C6]                 # files for one alias → vcsl:glock/loud C6
    (stdlib only; `vcsl` lists through mix.py's resolver, so run it with the mix.py deps: uv run --with librosa …)

Mixkit's search box ignores ?q= in plain HTTP, so this reads the tag pages (/free-sound-effects/<tag>/) and
the genre pages (/free-stock-music/<genre>/?page=N) instead. Pages are cached for 7 days in
~/.cache/motion-video/mixkit-pages/ and fetched at most one every 1.5 s — be gentle with the site.
Every row prints the ref to paste into sound.json. A title is not a sound: measure the pick (beats.py for
music, mix.py + verify_audio.py for SFX) and let a human listen to the shortlist.
"""
import html
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CACHE = Path.home() / ".cache/motion-video/mixkit-pages"
TTL = 7 * 86400
_last = [0.0]


def page(path: str) -> str:
    """GET https://mixkit.co/<path> through the cache, ≥ 1.5 s between network requests."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") + ".html")
    if f.exists() and time.time() - f.stat().st_mtime < TTL:
        return f.read_text()
    wait = 1.5 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request("https://mixkit.co/" + path.lstrip("/"), headers={"User-Agent": "Mozilla/5.0 (motion-video find_sound)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body, final = r.read().decode("utf8", "ignore"), r.geturl()
    except urllib.error.HTTPError as e:
        if e.code != 404:
            sys.exit(f"find_sound: {path}: HTTP {e.code}")
        body, final = "", ""
    _last[0] = time.time()
    if final and final.split("?")[0].rstrip("/") != ("https://mixkit.co/" + path.lstrip("/")).split("?")[0].rstrip("/"):
        print(f"  ({path} → {final})", file=sys.stderr)  # e.g. genre "cinematic" lives at tag/cinematic
    if body:
        f.write_text(body)  # empty answers aren't cached
    return body


def cards(h: str) -> list:
    out = []
    for c in h.split('class="item-grid__item"')[1:]:
        i = re.search(r'data-audio-player-item-id-value="(\d+)"', c)
        if not i:
            continue
        title = re.search(r'item-grid-card__title">\s*([^<]+?)\s*<', c)
        by = re.search(r'preview__author">\s*by\s+([^<]+?)\s*<', c)
        dur = re.search(r'data-test-id="duration">\s*([\d:]+)', c)
        kind = re.search(r'data-audio-player-item-type-value="(\w+)"', c)
        out.append({
            "id": int(i.group(1)), "kind": kind.group(1) if kind else "?",
            "title": html.unescape(title.group(1)) if title else "?", "by": html.unescape(by.group(1)) if by else "",
            "len": dur.group(1) if dur else "?",
            "tags": [html.unescape(t) for t in re.findall(r'meta-links__link"[^>]*href="[^"]+">([^<]+)<', c)],
        })
    return out


def secs(s: str) -> float:
    try:
        m, sec = s.split(":")
        return int(m) * 60 + int(sec)
    except ValueError:
        return 0.0


def show(rows, grep, max_len, prefix):
    for r in rows:
        blob = " ".join([r["title"], r["by"], *r["tags"]]).lower()
        if grep and not all(g in blob for g in grep):
            continue
        if max_len and secs(r["len"]) > max_len:
            continue
        by = f"  by {r['by']}" if r["by"] else ""
        print(f"  {prefix}{r['id']:<6} {r['len']:>5}  {r['title']}{by}  · {', '.join(r['tags'][:6])}")


def main():
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
    if not pos:
        sys.exit(__doc__)
    what, args = pos[0], pos[1:]
    grep = [g.lower() for g in (opt("--grep") or "").split(",") if g]
    max_len = float(opt("--max-len", 0))

    if what == "sfx":
        if not args:
            tags = sorted(set(re.findall(r'href="/free-sound-effects/([a-z0-9-]+)/"', page("free-sound-effects/whoosh/"))))
            print(f"{len(tags)} SFX tags: " + " ".join(tags))
            return
        for tag in args:
            rows = cards(page(f"free-sound-effects/{tag}/"))
            print(f"== sfx/{tag}: {len(rows)}" + ("" if rows else " (no such tag? `find_sound.py sfx` lists them)"))
            show(rows, grep, max_len, "mixkit-sfx:")
        return

    if what == "music":
        if not args:
            h = page("free-stock-music/")
            for kind in ("", "mood/", "instrument/", "tag/"):
                found = sorted(set(re.findall(rf'href="/free-stock-music/{kind}([a-z0-9-]+)/"', h)) - {"mood", "instrument", "tag"})
                print(f"{kind.rstrip('/') or 'genre'} ({len(found)}): " + " ".join(kind + f for f in found))
            return
        pages = int(opt("--pages", 2))
        for g in args:
            seen, rows, used = set(), [], 0
            for n in range(1, pages + 1):
                got = [r for r in cards(page(f"free-stock-music/{g}/" + (f"?page={n}" if n > 1 else ""))) if r["id"] not in seen]
                if not got:  # past the last page (or a redirect back to page 1)
                    break
                seen |= {r["id"] for r in got}
                rows, used = rows + got, n
            print(f"== music/{g}: {len(rows)} tracks from {used} page(s)")
            show(rows, grep, max_len, "mixkit-music:")
        print("next: uv run --with librosa python beats.py mixkit-music:<id> --len <film s>  (tempo, drop, cut window)")
        return

    if what == "vcsl":
        sys.path.insert(0, str(Path(__file__).parent))
        from mix import VCSL_ALIAS, vcsl_find
        if not args:
            for k, v in VCSL_ALIAS.items():
                print(f"  vcsl:{k:<16} {v}")
            print("then: find_sound.py vcsl <alias> [words] → files; ref = vcsl:<alias>/<words>[@n]")
            return
        ref = args[0] + ("/" + " ".join(args[1:]) if len(args) > 1 else "")
        hits = vcsl_find(ref)
        print(f"== vcsl:{ref}: {len(hits)} file(s) (CC0)")
        for i, p in enumerate(hits, 1):
            print(f"  @{i:<3} {p.rsplit('/', 1)[-1]:<48} {p.rsplit('/', 1)[0]}")
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
