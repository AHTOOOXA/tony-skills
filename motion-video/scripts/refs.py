#!/usr/bin/env python3
"""refs.py: a local, searchable database of published AI motion videos and their prompts.

Joins three public indexes on the tweet/status id:
  zhuyansen/jasonzhu.ai  (~1.4k posts >= 5k views; views, bookmarks, size, curated prompt text)
  claudevideo.org        (~1.3k videos; views, visual tags, theme; prompt on each video page)
  Skillry                (~500 videos; tech tags, a remake page; "prompt" is often just the post text)

  python3 refs.py update [--fetch-prompts N]
  python3 refs.py search [words...] [--tag T] [--category C] [--aspect 9:16] [--tech three.js]
                         [--author H] [--has-prompt] [--min-views N]
                         [--sort views|saves|saves-per-view|recent] [-n 10] [--full]
  python3 refs.py show <id|url|slug>
  python3 refs.py facets            # which tags, categories, tech values exist

Cache: ~/.cache/motion-video/refs.json (re-fetched automatically when missing or older than 14 days).
Stdlib only.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.request

CACHE_DIR = os.path.expanduser("~/.cache/motion-video")
CACHE = os.path.join(CACHE_DIR, "refs.json")
PROMPT_DIR = os.path.join(CACHE_DIR, "claudevideo-prompts")
MAX_AGE_DAYS = 14
UA = "motion-video-refs/1.0 (+https://github.com; personal research cache)"

GH_SOURCES = {
    "zhuyansen": ("zhuyansen/jasonzhu.ai", "src/content/opus-prompts/cases.json"),
    "skillry": ("yihui-dev/awesome-opus5-5-videos", "data/videos.json"),
}
CV_WALL = "https://claudevideo.org/wall.json"
CV_PAGE = "https://claudevideo.org/videos/{}"

# One vocabulary for the three sources' categories.
CATEGORY_ALIASES = {
    "stories": ["story"], "story": ["story"], "education": ["explainer"], "explainer": ["explainer"],
    "art3d": ["3d", "art"], "3d": ["3d"], "art": ["art"], "motion": ["motion"], "product": ["product"],
    "production": ["production"], "game": ["game"], "interactive": ["interactive"],
    "comparison": ["comparison"],
}
TIERS = {0: "with the phrase in title/summary/tags", 1: "with the phrase only in the prompt or post text",
         2: "with every word in title/summary/tags, not as a phrase", 3: "with the words scattered (loose)"}
# Prompt quality: full (a real brief), brief (a short real prompt), partial (caption or paraphrase).
RANK = {"full": 3, "brief": 2, "partial": 1}


# ---------------------------------------------------------------- fetching

def http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def gh_raw(repo, path):
    if shutil.which("gh"):
        p = subprocess.run(["gh", "api", f"repos/{repo}/contents/{path}",
                            "-H", "Accept: application/vnd.github.raw"],
                           capture_output=True, text=True, timeout=120)
        if p.returncode == 0 and p.stdout.strip():
            return json.loads(p.stdout)
        print(f"  gh api failed for {repo} ({p.stderr.strip()[:120]}); trying raw.githubusercontent.com",
              file=sys.stderr)
    return json.loads(http_get(f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"))


def status_id(url):
    m = re.search(r"/status(?:es)?/(\d+)", url or "")
    return m.group(1) if m else None


def norm_text(s):
    s = re.sub(r"https?://\S+", "", s or "")
    return re.sub(r"\W+", "", s.lower())


def norm_key(s):
    return re.sub(r"[^0-9a-z\u0080-￿]+", "", (s or "").lower())


def aspect_of(w, h):
    if not w or not h:
        return None
    r = w / h
    if r >= 1.5:
        return "16:9"
    if r >= 1.15:
        return "4:3"
    if r > 0.87:
        return "1:1"
    if r >= 0.7:
        return "4:5"
    return "9:16"


# ---------------------------------------------------------------- merging

def blank(tid):
    return {"id": tid, "url": None, "author": None, "author_name": None, "posted": None,
            "title": None, "title_zh": None, "summary": None, "post_text": None, "lang": None,
            "categories": [], "tags": [], "tech": [],
            "views": None, "likes": None, "bookmarks": None, "reposts": None,
            "width": None, "height": None, "aspect": None, "duration": None,
            "prompts": [], "cv_has_prompt": None, "reference_assets": None,
            "cv_slug": None, "skillry_url": None, "mp4": None, "poster": None, "sources": []}


def add_unique(lst, items):
    for x in items:
        if x and x not in lst:
            lst.append(x)


def maxnum(a, b):
    vals = [v for v in (a, b) if isinstance(v, (int, float))]
    return max(vals) if vals else None


def merge_zhu(rec, c):
    rec["sources"].append("zhuyansen")
    rec["url"] = rec["url"] or c.get("url")
    a = c.get("author") or {}
    rec["author"] = rec["author"] or a.get("handle")
    rec["author_name"] = rec["author_name"] or a.get("name")
    rec["posted"] = rec["posted"] or c.get("postedAt")
    t, s = c.get("title") or {}, c.get("summary") or {}
    rec["title"] = t.get("en") or rec["title"]
    rec["title_zh"] = t.get("zh")
    rec["summary"] = s.get("en") or rec["summary"]
    rec["lang"] = rec["lang"] or c.get("lang")
    add_unique(rec["categories"], CATEGORY_ALIASES.get(c.get("category") or "", [c.get("category")]))
    add_unique(rec["tech"], [norm_key(x) for x in c.get("tools") or []])
    st = c.get("stats") or {}
    for k in ("views", "likes", "bookmarks", "reposts"):
        rec[k] = maxnum(rec[k], st.get(k))
    v = c.get("video") or {}
    rec["width"], rec["height"] = v.get("width"), v.get("height")
    rec["duration"] = v.get("durationSec") or rec["duration"]
    rec["mp4"] = v.get("mp4") or rec["mp4"]
    rec["poster"] = rec["poster"] or v.get("poster")
    rec["reference_assets"] = c.get("referenceAssets")
    p = c.get("prompt")
    if p and p.get("text"):
        rec["prompts"].append({"source": f"zhuyansen/{p.get('source')}",
                               "quality": "full" if p.get("kind") == "full" else "brief",
                               "text": p["text"], "url": p.get("sourceUrl")})


def merge_cv(rec, i):
    rec["sources"].append("claudevideo")
    a = i.get("author") or {}
    rec["url"] = rec["url"] or (f"https://x.com/{a.get('screenName')}/status/{i['id']}"
                                if a.get("screenName") else None)
    rec["author"] = rec["author"] or a.get("screenName")
    rec["author_name"] = rec["author_name"] or a.get("name")
    rec["posted"] = rec["posted"] or i.get("createdAt")
    rec["title"] = rec["title"] or i.get("title")
    rec["summary"] = rec["summary"] or i.get("summary")
    rec["post_text"] = i.get("text") or rec["post_text"]
    rec["lang"] = rec["lang"] or i.get("lang")
    add_unique(rec["categories"], CATEGORY_ALIASES.get((i.get("theme") or "").lower(),
                                                        [(i.get("theme") or "").lower()]))
    add_unique(rec["tags"], i.get("visualTags") or [])
    add_unique(rec["tech"], [norm_key(x) for x in i.get("toolsReported") or []])
    m = i.get("metrics") or {}
    for k in ("views", "likes", "bookmarks", "reposts"):
        rec[k] = maxnum(rec[k], m.get(k))
    media = (i.get("media") or [{}])[0]
    if not rec["duration"] and media.get("durationMs"):
        rec["duration"] = round(media["durationMs"] / 1000)
    rec["mp4"] = rec["mp4"] or media.get("publicUrl")
    rec["poster"] = rec["poster"] or media.get("posterPublicUrl")
    rec["cv_slug"] = i.get("slug")
    rec["cv_has_prompt"] = bool(i.get("hasPrompt"))


def merge_sk(rec, s):
    rec["sources"].append("skillry")
    rec["url"] = rec["url"] or s.get("post_url")
    rec["author"] = rec["author"] or s.get("author")
    rec["posted"] = rec["posted"] or s.get("added")
    add_unique(rec["categories"], CATEGORY_ALIASES.get(s.get("category") or "", [s.get("category")]))
    add_unique(rec["tech"], [norm_key(x) for x in s.get("tech_tags") or []])
    rec["skillry_url"] = s.get("skillry_url")
    rec["poster"] = rec["poster"] or s.get("poster_url")
    if s.get("prompt"):
        rec["prompts"].append({"source": "skillry",
                               "quality": "partial" if s.get("prompt_partial") else "full",
                               "text": s["prompt"], "url": s.get("skillry_url")})


def cv_prompt_cached(slug):
    path = os.path.join(PROMPT_DIR, slug + ".txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None


def finish(rec):
    """Flags, derived fields and the best prompt."""
    if rec["cv_slug"]:
        txt = cv_prompt_cached(rec["cv_slug"])
        if txt:
            rec["prompts"].append({"source": "claudevideo", "quality": "full", "text": txt,
                                   "url": CV_PAGE.format(rec["cv_slug"])})
    post = norm_text(rec["post_text"])
    for p in rec["prompts"]:
        t = norm_text(p["text"])
        p["is_post_text"] = bool(post and t and (t in post or post in t)) if post else None
        if p["source"] == "skillry" and p["is_post_text"] and p["quality"] == "full":
            p["quality"] = "brief"  # the post itself was the prompt
    rec["prompts"].sort(key=lambda p: (-RANK[p["quality"]], -len(p["text"])))
    best = rec["prompts"][0] if rec["prompts"] else None
    rec["prompt"] = best["text"] if best else None
    rec["prompt_quality"] = best["quality"] if best else None
    rec["prompt_source"] = best["source"] if best else None
    rec["prompt_is_post_text"] = best["is_post_text"] if best else None
    rec["aspect"] = aspect_of(rec["width"], rec["height"]) or ("9:16" if "vertical" in rec["tags"] else None)
    v, b = rec["views"], rec["bookmarks"]
    rec["saves_per_view"] = round(b / v, 5) if v and b is not None and v >= 1 else None
    return rec


def build(raw):
    recs = {}

    def get(tid):
        if tid not in recs:
            recs[tid] = blank(tid)
        return recs[tid]

    for c in raw.get("zhuyansen") or []:
        tid = c.get("id") or status_id(c.get("url"))
        if tid:
            merge_zhu(get(tid), c)
    for i in raw.get("claudevideo") or []:
        tid = i.get("id") if str(i.get("id", "")).isdigit() else None
        if tid:
            merge_cv(get(tid), i)
    for s in raw.get("skillry") or []:
        tid = status_id(s.get("post_url"))
        if tid:
            merge_sk(get(tid), s)
    return [finish(r) for r in recs.values()]


# ---------------------------------------------------------------- cache

def fetch_raw():
    raw, ok = {}, []
    print("refs: downloading zhuyansen, claudevideo, skillry...", file=sys.stderr)
    for name, (repo, path) in GH_SOURCES.items():
        try:
            data = gh_raw(repo, path)
            raw[name] = data["cases"] if isinstance(data, dict) else data
            ok.append(name)
        except Exception as e:  # keep going with the others
            print(f"  {name}: failed ({e})", file=sys.stderr)
    try:
        raw["claudevideo"] = json.loads(http_get(CV_WALL))
        ok.append("claudevideo")
    except Exception as e:
        print(f"  claudevideo: failed ({e})", file=sys.stderr)
    return raw, ok


def fetch_cv_prompts(records, n, delay=1.5):
    """Fetch claudevideo prompt pages for the top-n (by views) videos that have one there but none here."""
    os.makedirs(PROMPT_DIR, exist_ok=True)
    todo = [r for r in records if r["cv_slug"] and r["cv_has_prompt"]
            and RANK.get(r["prompt_quality"] or "", 0) < RANK["brief"]
            and cv_prompt_cached(r["cv_slug"]) is None]
    todo.sort(key=lambda r: -(r["views"] or 0))
    todo = todo[:n]
    print(f"refs: fetching {len(todo)} claudevideo prompt pages ({delay}s apart)...", file=sys.stderr)
    got = 0
    for k, r in enumerate(todo):
        try:
            page = http_get(CV_PAGE.format(r["cv_slug"]), timeout=30)
        except Exception as e:
            print(f"  {r['cv_slug']}: {e}", file=sys.stderr)
            continue
        txt = ""
        i, j = page.find("THE PROMPT"), page.find("MAKE ONE LIKE THIS")
        if i >= 0:
            seg = page[i:j if j > i else None]
            m = re.search(r"<pre[^>]*data-prompt-text[^>]*>(.*?)</pre>", seg, re.S)
            if m:
                txt = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        with open(os.path.join(PROMPT_DIR, r["cv_slug"] + ".txt"), "w", encoding="utf-8") as f:
            f.write(txt)  # empty file = checked, nothing there
        got += bool(txt)
        if k < len(todo) - 1:
            time.sleep(delay)
    print(f"  {got} prompts found", file=sys.stderr)
    return got


def save(db):
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False)
    os.replace(tmp, CACHE)


def update(fetch_prompts=0):
    raw, ok = fetch_raw()
    if not ok:
        sys.exit("refs: all sources failed; cache left as it was")
    raw_path = os.path.join(CACHE_DIR, "refs-raw.json")
    old = {}
    if len(ok) < 3 and os.path.exists(raw_path):  # reuse the last good copy of a failed source
        with open(raw_path, encoding="utf-8") as f:
            old = json.load(f)
        for k in ("zhuyansen", "claudevideo", "skillry"):
            if k not in raw and k in old:
                raw[k] = old[k]
                print(f"  {k}: using the previous download", file=sys.stderr)
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    records = build(raw)
    if fetch_prompts:
        if fetch_cv_prompts(records, fetch_prompts):
            records = build(raw)
    db = {"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
          "counts": {k: len(v) for k, v in raw.items()}, "records": records}
    save(db)
    n = len(records)
    multi = sum(len(r["sources"]) > 1 for r in records)
    hp = sum(r["prompt_quality"] in ("full", "brief") for r in records)
    print(f"refs: {n} posts ({multi} in 2+ sources), {hp} with a real prompt -> {CACHE}", file=sys.stderr)
    return db


def load(auto=True):
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            db = json.load(f)
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(db["fetched_at"])
        if age.days < MAX_AGE_DAYS or not auto:
            return db
        print(f"refs: cache is {age.days} days old (> {MAX_AGE_DAYS}); updating", file=sys.stderr)
    else:
        print("refs: no cache yet; running update", file=sys.stderr)
    return update()


# ---------------------------------------------------------------- output

def fmt_n(n):
    if n is None:
        return "?"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.0f}k" if n >= 1e4 else f"{n / 1e3:.1f}k"
    return str(n)


def first_line(s, width):
    s = " ".join((s or "").split())
    return s if len(s) <= width else s[: width - 1] + "…"


def haystack(r, deep):
    """deep=False: what the video is (title, summary, tags); deep=True adds post text and prompts."""
    parts = [r["title"], r["title_zh"], r["summary"], r["author"], r["author_name"],
             " ".join(r["tags"]), " ".join(r["categories"]), " ".join(r["tech"])]
    if deep:
        parts += [r["post_text"]] + [p["text"] for p in r["prompts"]]
    return " ".join(p for p in parts if p).lower()


def word_pattern(w):
    """Latin/Cyrillic words match at a word start ("draw" finds "drawn", "art" skips "start");
    a quoted "two words" arg is a phrase; CJK and other scripts match as substrings."""
    parts = [re.escape(p) for p in re.split(r"[\s\-_]+", w.lower()) if p]
    body = r"[\s\-_]*".join(parts)  # "line art" also finds "line-art", "lineart"
    if re.match(r"[0-9a-zÀ-ɏЀ-ӿ]", w.lower()):
        return re.compile(r"(?<![0-9a-zÀ-ɏЀ-ӿ])" + body)
    return re.compile(body)


def match_list(values, wanted):
    vals = {norm_key(v) for v in values}
    return all(norm_key(w) in vals for w in wanted)


def search(db, a):
    recs = db["records"]
    words = [word_pattern(w) for w in a.words if w.strip()]
    phrase = word_pattern(" ".join(a.words)) if len(words) > 1 else None
    out = []
    for r in recs:
        if a.tag and not match_list(r["tags"], a.tag):
            continue
        if a.category and not match_list(r["categories"], a.category):
            continue
        if a.tech and not match_list(r["tech"], a.tech):
            continue
        if a.author and norm_key(a.author.lstrip("@")) != norm_key(r["author"]):
            continue
        if a.aspect:
            want = a.aspect.lower()
            if want in ("vertical", "portrait"):
                if r["aspect"] not in ("9:16", "4:5"):
                    continue
            elif want in ("horizontal", "landscape"):
                if r["aspect"] not in ("16:9", "4:3"):
                    continue
            elif want == "square":
                if r["aspect"] != "1:1":
                    continue
            elif r["aspect"] != want:
                continue
        if a.has_prompt and r["prompt_quality"] not in ("full", "brief"):
            continue
        if (r["views"] or 0) < a.min_views:
            continue
        tier = 0
        if words:
            deep, desc = haystack(r, True), haystack(r, False)
            if not all(w.search(deep) for w in words):
                continue
            if phrase and phrase.search(desc):
                tier = 0
            elif phrase and phrase.search(deep):
                tier = 1
            elif all(w.search(desc) for w in words):
                tier = 2 if phrase else 0
            else:
                tier = 3 if phrase else 1
        out.append({**r, "_tier": tier})
    keys = {
        "views": lambda r: r["views"] or 0,
        "saves": lambda r: r["bookmarks"] or 0,
        "saves-per-view": lambda r: r["saves_per_view"] or 0,
        "recent": lambda r: r["posted"] or "",
    }
    if a.sort == "saves-per-view":  # tiny posts give noisy ratios
        floor = a.min_views or 5000
        out = [r for r in out if (r["views"] or 0) >= floor]
    out.sort(key=keys[a.sort], reverse=True)
    out.sort(key=lambda r: r["_tier"])  # stable: described-as matches first, prompt-only after
    return out


def print_compact(rows, total, a):
    shown = rows[: a.n]
    print(f"{total} match{'es' if total != 1 else ''}; top {len(shown)} by {a.sort}")
    for k, r in enumerate(shown, 1):
        if a.words and (k == 1 or shown[k - 2]["_tier"] != r["_tier"]):
            n = sum(x["_tier"] == r["_tier"] for x in rows)
            label = TIERS[r["_tier"]] if len(a.words) > 1 else TIERS[r["_tier"]].replace("with the phrase ", "found ")
            print(f"\n-- {n} {label} --")
        spv = f"{r['saves_per_view'] * 100:.1f}%" if r["saves_per_view"] is not None else "?"
        meta = " · ".join(x for x in [
            f"@{r['author']}" if r["author"] else None, r["aspect"],
            f"{r['duration']}s" if r["duration"] else None, (r["posted"] or "")[:10] or None,
            ",".join(r["categories"][:2]) or None] if x)
        print(f"\n{k:>2}. {fmt_n(r['views']):>6} views {fmt_n(r['bookmarks']):>6} saves {spv:>5} s/v   {meta}")
        title = r["title"] or first_line(r["post_text"], 90)
        if title:
            print(f"    {first_line(title, 100)}")
        if r["tags"]:
            print(f"    tags: {', '.join(r['tags'][:6])}")
        if r["prompt"]:
            mark = r["prompt_quality"] + (", post text" if r["prompt_is_post_text"] else "")
            if a.full:
                print(f"    prompt ({mark}, {r['prompt_source']}):")
                print(textwrap.indent(r["prompt"].strip(), "      | ", lambda line: True))
            else:
                print(f"    prompt ({mark}): {first_line(r['prompt'], 110)}")
        elif r["cv_has_prompt"]:
            print(f"    prompt: on claudevideo, not fetched (update --fetch-prompts N, or open the page)")
        print(f"    {r['url'] or ''}   id {r['id']}")


def show(db, key):
    key = key.strip()
    tid = status_id(key) or (key if key.isdigit() else None)
    slug = key.rstrip("/").rsplit("/", 1)[-1]
    for idx, r in enumerate(db["records"]):
        if (tid and r["id"] == tid) or r["cv_slug"] == slug or (
                r["skillry_url"] and r["skillry_url"].rstrip("/").endswith("/" + slug)):
            break
    else:
        sys.exit(f"refs: nothing matches {key!r}")
    if RANK.get(r["prompt_quality"] or "", 0) < RANK["brief"] and r["cv_has_prompt"] and r["cv_slug"]:
        if fetch_cv_prompts([r], 1, delay=0):
            r = finish({**r, "prompts": [p for p in r["prompts"] if p["source"] != "claudevideo"]})
            db["records"][idx] = r
            save(db)
    spv = f"{r['saves_per_view'] * 100:.2f}%" if r["saves_per_view"] is not None else "?"
    rows = [
        ("post", r["url"]), ("author", f"@{r['author']} ({r['author_name'] or ''})"),
        ("posted", r["posted"]), ("title", r["title"]), ("summary", r["summary"]),
        ("stats", f"{r['views']} views · {r['likes']} likes · {r['bookmarks']} saves · {spv} s/v"),
        ("video", f"{r['width'] or '?'}x{r['height'] or '?'} ({r['aspect'] or 'aspect ?'}) · "
                  f"{r['duration'] or '?'} s"),
        ("categories", ", ".join(r["categories"])), ("tags", ", ".join(r["tags"])),
        ("tech/tools", ", ".join(r["tech"])),
        ("ref assets", r["reference_assets"]), ("mp4", r["mp4"]), ("poster", r["poster"]),
        ("claudevideo", CV_PAGE.format(r["cv_slug"]) if r["cv_slug"] else None),
        ("skillry", r["skillry_url"]), ("sources", ", ".join(r["sources"])),
    ]
    for k, v in rows:
        if v not in (None, "", "@None ()"):
            print(f"{k:>12}: {v}")
    if r["post_text"]:
        print("\n--- post text ---\n" + r["post_text"].strip())
    if not r["prompts"]:
        print("\n(no prompt published in any of the indexes)")
    for p in r["prompts"]:
        flag = ", same as post text" if p["is_post_text"] else ""
        print(f"\n--- prompt: {p['quality']}{flag} · {p['source']} · {p.get('url') or ''} ---")
        print(p["text"].strip())


def facets(db):
    from collections import Counter
    for field in ("categories", "tags", "tech"):
        c = Counter(x for r in db["records"] for x in r[field])
        top = ", ".join(f"{k} {n}" for k, n in c.most_common(40))
        print(f"{field}: {top}\n")
    c = Counter(r["aspect"] or "unknown" for r in db["records"])
    print("aspect: " + ", ".join(f"{k} {n}" for k, n in c.most_common()))
    q = Counter(r["prompt_quality"] or "none" for r in db["records"])
    print("prompt: " + ", ".join(f"{k} {n}" for k, n in q.most_common()))
    print(f"\nfetched {db['fetched_at']} · {len(db['records'])} posts · raw {db['counts']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="download and join the three indexes")
    u.add_argument("--fetch-prompts", type=int, default=0, metavar="N",
                   help="also fetch claudevideo prompt pages for the top-N videos lacking a prompt")
    s = sub.add_parser("search", help="filter and rank")
    s.add_argument("words", nargs="*", help='all must appear in title/summary/post/prompt/tags (any language); '
                                            'words match at a word start; quote "a phrase"')
    s.add_argument("--tag", action="append", help="claudevideo visual tag, e.g. vertical, hand-drawn (repeatable)")
    s.add_argument("--category", action="append", help="motion, explainer, product, story, 3d, game… (repeatable)")
    s.add_argument("--tech", action="append", help="three.js, canvas, svg, gsap, remotion… (repeatable)")
    s.add_argument("--aspect", help="16:9, 4:3, 1:1, 4:5, 9:16, or vertical/landscape/square")
    s.add_argument("--author", help="X handle")
    s.add_argument("--has-prompt", action="store_true", help="a real prompt (not just a caption)")
    s.add_argument("--min-views", type=int, default=0, help="saves-per-view defaults to 5000")
    s.add_argument("--sort", default="views", choices=["views", "saves", "saves-per-view", "recent"])
    s.add_argument("-n", type=int, default=10)
    s.add_argument("--full", action="store_true", help="print whole prompts")
    s.add_argument("--json", action="store_true", help="matching records as JSON")
    sh = sub.add_parser("show", help="one record with every prompt we have")
    sh.add_argument("key", help="status id, x.com URL, claudevideo slug/URL or skillry URL")
    sub.add_parser("facets", help="values you can filter on, with counts")
    a = ap.parse_args()

    if a.cmd == "update":
        update(a.fetch_prompts)
        return
    db = load()
    if a.cmd == "search":
        rows = search(db, a)
        if a.json:
            json.dump(rows[: a.n], sys.stdout, ensure_ascii=False, indent=1)
            print()
        else:
            print_compact(rows, len(rows), a)
    elif a.cmd == "show":
        show(db, a.key)
    elif a.cmd == "facets":
        facets(db)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
