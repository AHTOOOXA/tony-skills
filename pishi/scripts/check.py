#!/usr/bin/env python3
"""Deterministic Russian-prose linter for the `pishi` skill. Stdlib only.

Flags stop-words (infostyle groups), bureaucratese, passive/participles,
vagueness, Russian AI-tells, long sentences, and — with --source — numbers
that do not appear in the source material («цифры непонятно откуда»).

Usage:
  python3 check.py text.txt
  echo "текст" | python3 check.py -
  python3 check.py draft.txt --source notes.md --max-words 180 --no-greeting
  python3 check.py draft.txt --json

Exit code 1 if --min-score / --max-words / --no-greeting / --source checks fail.
Score = 100 - penalty points per 100 words (floor 0). It is a lens, not a judge:
a hit can be legitimate — the point is to *see* it and decide.
"""
import argparse, json, re, sys, unicodedata

# ---------- word lists (own compilation; stems, matched with word boundaries) ----------

HARD = [  # AI-tells & throat-clearing that almost never survive a real editor
    r"в современном мире", r"на сегодняшний день", r"в настоящее время", r"в наше время", r"в наши дни",
    r"стоит отметить", r"следует отметить", r"важно отметить", r"нельзя не отметить", r"важно понимать",
    r"важно помнить", r"необходимо подчеркнуть", r"хочется отметить", r"хотелось бы отметить",
    r"не секрет,? что", r"ни для кого не секрет", r"как известно", r"всем известно",
    r"давайте разбер[её]мся", r"давайте рассмотрим", r"давайте посмотрим",
    r"подводя итог", r"в заключение", r"резюмируя", r"^таким образом,", r"^итак,",
    r"надеюсь,? (это )?помо", r"если (у вас )?(возникнут|будут|появятся) вопросы", r"буду рад помочь",
    r"обращайтесь", r"спасибо за внимание", r"с уважением", r"отличный вопрос", r"хороший вопрос",
    r"мощн(ый|ым) инструмент", r"открывает новые (горизонты|возможности)", r"играет (ключевую|важную) роль",
    r"ключевую роль", r"имеет (важное|большое) значение", r"оказывает (существенное |значительное )?влияние",
    r"в рамках", r"в целях", r"в части", r"в контексте", r"в разрезе", r"имеет место", r"имеет место быть",
    r"на (ежедневной|постоянной|регулярной) основе", r"в конечном (итоге|сч[её]те)", r"^как правило,",
    r"широкий спектр", r"целый ряд", r"ряд преимуществ",
    r"в конце дня", r"делает смысл", r"хорош(ие|ая) новост", r"плох(ие|ая) новост",
    r"как (ты|вы) и (просил|просили|хотел|хотели)", r"небольшой апдейт", r"хотел (бы )?(рассказать|поделиться|сообщить)",
    r"данн(ый|ая|ое|ому|ой|ом|ую|ыми)\b",
]
PARALLEL = [r"не просто \S+(\s\S+){0,4},? а ", r"это не \S+(\s\S+){0,4}[,—–-] (а|это) ", r"дело не в \S+(\s\S+){0,3},? а в "]
CALQUE = [  # English wearing Russian clothes / light-verb constructions
    r"\bявля(ется|ются|лся|лась|лось|лись|ться)\b", r"представля(ет|ют) собой", r"носит (\w+ )?характер",
    r"(имеет|дает|да[её]т|предоставляет|предоставит) возможность", r"\bпозволя(ет|ют)\b",
    r"\bобеспечива(ет|ют)\b", r"\bосуществля(ет|ют|ть|ется|ются)\b", r"\bпроизвод(ит|ят|ится|ятся)\b",
    r"\bфункционал\b", r"опыт пользователя", r"проактивно", r"\bкоммуницир", r"\bменеджерить",
    r"на (моей|вашей|твоей|нашей|их) стороне", r"\bэто про\b", r"\bфокусир",
]
INTRO = [  # вводные и связки
    r"безусловно", r"бесспорно", r"без сомнения", r"\bконечно\b", r"разумеется", r"\bочевидно\b", r"естественно",
    r"несомненно", r"к сожалению", r"к счастью", r"честно говоря", r"если честно", r"по правде говоря", r"признаться",
    r"на мой взгляд", r"по моему мнению", r"как мне кажется", r"мне кажется", r"\bкстати\b", r"между прочим",
    r"\bвпрочем\b", r"вообще говоря", r"\bсобственно\b", r"по сути", r"в принципе", r"в общем", r"в общем-то",
    r"во-первых", r"во-вторых", r"в-третьих", r"\bнаконец\b", r"\bдалее\b", r"\bдопустим\b", r"\bскажем\b",
    r"другими словами", r"иными словами", r"\bточнее\b", r"\bвернее\b", r"более того", r"кроме того", r"помимо (этого|того)",
    r"при этом", r"^также\b", r"тем не менее", r"в свою очередь", r"в частности", r"действительно", r"на самом деле",
    r"фактически", r"практически", r"буквально", r"\bдовольно\b", r"\bвесьма\b", r"\bкрайне\b", r"абсолютно",
    r"совершенно", r"\bочень\b", r"в целом", r"в итоге", r"по большому сч[её]ту", r"так или иначе", r"в любом случае",
]
EVAL = [  # оценки — заменяются фактом или удаляются
    r"эффективн", r"качественн", r"уникальн", r"над[её]жн", r"оптимальн", r"современн", r"инновационн", r"удобн",
    r"\bважн", r"актуальн", r"значительн", r"существенн", r"серь[её]зн", r"огромн", r"\bмощн", r"отличн", r"прекрасн",
    r"замечательн", r"\bлучш", r"идеальн", r"превосходн", r"великолепн", r"комфортн", r"выгодн", r"профессиональн",
    r"компетентн", r"успешн", r"продвинут", r"передов", r"интересн", r"полезн", r"\bценн", r"максимальн", r"глубок(ий|ая|ое|о) (анализ|понимание|проработк)",
    r"тщательн", r"детальн", r"всесторонн", r"комплексн", r"системн(ый|ая|ое|о) подход", r"грамотн", r"ч[её]тк", r"прозрачн",
    r"стабильн", r"устойчив", r"проверенн", r"гарантированн", r"кардинальн", r"оперативн", r"своевременн", r"корректн",
    r"высок(ое|ий|ого|им) (качеств|уровен|уровн)", r"по-настоящему", r"настоящ(ий|ая|ее) ", r"по праву", r"заслуженно",
]
BUREAU = [  # канцелярит и отглагольное
    r"осуществлени", r"обеспечени", r"реализаци", r"внедрени", r"функционировани", r"взаимодействи", r"проведени",
    r"выполнени", r"направлени", r"мероприяти", r"использовани", r"осуществить", r"произвести", r"обеспечить",
    r"в связи с", r"с целью", r"по причине", r"по вопросу", r"в отношении", r"в области", r"в сфере", r"в процессе",
    r"при помощи", r"посредством", r"\bпут[её]м\b", r"в случае,? если", r"в ходе", r"по итогам", r"на предмет",
    r"в соответствии с", r"в установленном порядке", r"надлежащ", r"соответствующ(ий|ие|ая|ее|им|их|его|ей)\b",
    r"\bнеобходимо\b", r"\bтребуется\b", r"\bследует\b", r"оказать содействие", r"принять меры", r"(проводить|вести|провести) работу",
    r"в настоящий момент", r"на (данный|текущий) момент", r"вышеуказанн", r"нижеследующ", r"вышеупомянут",
    r"уведомля(ю|ем)", r"довожу до сведения", r"доводим до (вашего )?сведения", r"прошу (вас )?(рассмотреть|обратить внимание)",
    r"(производится|осуществляется|выполняется|проводится|планируется|предполагается|рассматривается|используется|обеспечивается)\b",
]
VAGUE = [  # неопределённое
    r"\b(более|свыше|около|порядка|почти|не менее|не более) \d", r"\bнекотор(ые|ых|ым|ой|ая|ое)\b", r"в ряде случаев",
    r"\bразличн", r"\bмногие\b", r"\bмножество\b", r"\bмасса\b", r"\bзачастую\b", r"\bнередко\b", r"периодически",
    r"в основном", r"в большинстве случаев", r"определ[её]нн(ые|ых|ый|ая|ое|ую)\b", r"те или иные", r"тот или иной",
    r"и т\.\s?д\.", r"и т\.\s?п\.", r"и други(е|х)\b", r"и прочее", r"и так далее", r"как(ой|ие|ая|ое)-то\b", r"\bнек(ий|ая|ое)\b",
    r"\bчто-то\b", r"\bкто-то\b", r"\bот \d[\d\s]*\s?(₽|руб|\$|€|֏|тыс)", r"\bсколько-то\b", r"\bнесколько\b",
]
TRANSITION_OPENERS = r"^(также|кроме того|помимо этого|при этом|таким образом|в целом|в итоге|более того|важно|стоит|следует|отметим|заметим|напомним|в заключение|подводя)\b"
GREETING = r"^(привет|здравствуйте|добрый день|доброе утро|добрый вечер|хай|йо|hi|hello)\b"

PENALTY = {"hard": 8, "parallel": 3, "calque": 4, "intro": 2, "eval": 2, "bureau": 3, "vague": 2, "passive": 2, "participle": 1,
           "transition": 2, "long_sentence": 2, "dash_excess": 1, "triad_excess": 1, "bold_excess": 1, "emoji_excess": 1,
           "header_in_short": 2, "paren_excess": 1, "not_only": 2, "greeting": 3, "foreign_number": 6, "english_prose": 3}

# ---------- helpers ----------

def norm(s):
    return unicodedata.normalize("NFC", s).lower().replace("ё", "е")

def words(text):
    # «5 595» / «2 500 ₽» — one number, one word
    t = re.sub(r"(?<=\d)[ \u00a0](?=\d{3}\b)", "", norm(text))
    return re.findall(r"[а-яa-z0-9]+(?:[-.,][а-яa-z0-9]+)*", t)

def sentences(text):
    # line breaks are sentence boundaries too: bullets, headers, one-line paragraphs
    out = []
    for line in text.strip().splitlines():
        line = re.sub(r"^\s*(?:[•\-*]|\d+[.)])\s*", "", line.strip())
        if not line: continue
        parts = re.split(r"(?<=[.!?…])\s+(?=[«\"A-ZА-ЯЁ0-9])", line)
        out += [p for p in parts if len(words(p)) > 0]
    return out

def find_all(patterns, text, flags=re.M):
    hits = []
    n = norm(text)
    for p in patterns:
        for m in re.finditer(p, n, flags):
            hits.append((m.start(), m.group(0)))
    return hits

def line_of(text, pos):
    return text.count("\n", 0, pos) + 1

def quote_at(text, pos, width=60):
    n = norm(text)
    s = max(0, pos - width // 2); e = min(len(n), pos + width // 2)
    return ("…" if s else "") + text[s:e].replace("\n", " ") + ("…" if e < len(n) else "")

def numbers_in(text):
    """Digit sequences, normalized: drop thousand separators, keep decimals."""
    out = set()
    for m in re.finditer(r"\d[\d  .,]*\d|\d", text):
        raw = m.group(0)
        clean = re.sub(r"[  ]", "", raw)
        clean = clean.rstrip(".,")
        out.add(clean)
        out.add(clean.replace(",", "."))
        out.add(re.sub(r"[.,]", "", clean))
    return out

# ---------- main analysis ----------

def analyze(text, source=None, max_words=None, no_greeting=False):
    W = words(text); nw = max(len(W), 1)
    S = sentences(text)
    findings = {}
    def add(cat, pos, snippet, note=""):
        findings.setdefault(cat, []).append({"line": line_of(text, pos), "hit": snippet, "context": quote_at(text, pos), "note": note})

    for cat, pats in (("hard", HARD), ("parallel", PARALLEL), ("calque", CALQUE), ("intro", INTRO), ("eval", EVAL), ("bureau", BUREAU), ("vague", VAGUE)):
        for pos, hit in find_all(pats, text):
            add(cat, pos, hit)

    # passive: был/была/было/были + short participle
    for m in re.finditer(r"\b(был|была|было|были)\s+([а-я]+(?:н|на|но|ны|т|та|то|ты))\b", norm(text)):
        add("passive", m.start(), m.group(0))
    # participles (approximate; own stoplist for common adjectives)
    STOP_ADJ = {"длинный","странный","ценный","сонный","данный","временный","современный","постоянный","обыкновенный","сторонний","старинный","подлинный","истинный","бесценный","единственный","многочисленный","мгновенный","весенний","осенний","зимний","летний","утренний","вечерний","ранний","поздний","внутренний","внешний","средний","нижний","верхний","последний","прежний","нынешний","домашний","соседний","лишний","ближний","дальний","крайний","дневной","ночной"}
    for m in re.finditer(r"\b[а-я]{3,}(?:ующ|ющ|ащ|ящ|вш|енн|анн|янн|[её]нн|ённ)(?:ий|ая|ое|ые|его|ей|им|их|ими|ем|ую|ым|ых|ой|ому|ом)\b", norm(text)):
        w = m.group(0)
        stem = re.sub(r"(ий|ая|ое|ые|его|ей|им|их|ими|ем|ую|ым|ых|ой|ому|ом)$", "", w)
        if any(a.startswith(stem) or stem.startswith(a[:-2]) for a in STOP_ADJ if len(a) > 4): continue
        add("participle", m.start(), w)

    # transition openers per sentence / line
    for m in re.finditer(TRANSITION_OPENERS, norm(text), re.M):
        add("transition", m.start(), m.group(0))
    for s in S:
        for m in re.finditer(TRANSITION_OPENERS, norm(s)):
            pos = norm(text).find(norm(s)[:40])
            if pos >= 0 and not any(f["line"] == line_of(text, pos) and f["hit"] == m.group(0) for f in findings.get("transition", [])):
                add("transition", pos, m.group(0))

    # long sentences
    longest = 0
    for s in S:
        n = len(words(s)); longest = max(longest, n)
        if n > 25:
            pos = norm(text).find(norm(s)[:40])
            add("long_sentence", max(pos, 0), f"{n} слов", s[:90] + ("…" if len(s) > 90 else ""))

    # AI structure signals
    dashes = len(re.findall(r"\s[—–]\s", text)); dash_rate = dashes * 100 / nw
    if dash_rate > 4:
        add("dash_excess", 0, f"{dashes} тире на {nw} слов ({dash_rate:.1f}/100)", "норма ≤ 4 на 100 слов")
    triads = re.findall(r"[а-яё«»\"\w-]+, [а-яё«»\"\w-]+ и [а-яё«»\"\w-]+", norm(text))
    if len(triads) > max(2, nw // 150):
        add("triad_excess", 0, f"{len(triads)} тройки «X, Y и Z»", "правило трёх — след нейросети, если везде")
    bolds = len(re.findall(r"\*\*[^*]+\*\*", text))
    if bolds > 3 and nw < 400:
        add("bold_excess", 0, f"{bolds} жирных выделений на {nw} слов")
    emojis = len(re.findall(r"[\U0001F300-\U0001FAFF☀-➿]", text))
    if emojis > 3:
        add("emoji_excess", 0, f"{emojis} эмодзи")
    headers = len(re.findall(r"^#{1,6}\s", text, re.M))
    if headers and nw < 200:
        add("header_in_short", 0, f"{headers} markdown-заголовков в тексте на {nw} слов", "короткому сообщению заголовки не нужны")
    parens = text.count("(")
    if parens > max(2, nw // 100):
        add("paren_excess", 0, f"{parens} скобок на {nw} слов", "скобки = «это неважно». Убрать или вытащить")
    not_only = len(re.findall(r"не только .{2,60}?, но и", norm(text)))
    if not_only > 1:
        add("not_only", 0, f"{not_only}× «не только…, но и»")
    if no_greeting:
        for m in re.finditer(GREETING, norm(text), re.M):
            add("greeting", m.start(), m.group(0), "рабочее сообщение — без приветствия")
    latin_words = [w for w in W if re.fullmatch(r"[a-z]{4,}", w)]
    if len(latin_words) > nw * 0.15:
        add("english_prose", 0, f"{len(latin_words)}/{nw} латинских слов", "английская проза в русском тексте?")

    # numbers not in source
    if source is not None:
        src_nums = numbers_in(source)
        for m in re.finditer(r"\d[\d  .,]*\d|\d", text):
            raw = m.group(0); clean = re.sub(r"[  ]", "", raw).rstrip(".,")
            variants = {clean, clean.replace(",", "."), re.sub(r"[.,]", "", clean)}
            if not (variants & src_nums):
                # tolerate trivial small ints (list numbering 1-3, ordinal-ish) only if standalone
                if clean.isdigit() and int(clean) <= 3 and re.match(r"^\s*\d[.)]", text[max(0, m.start()-1):m.start()+3]):
                    continue
                add("foreign_number", m.start(), raw.strip(), "числа нет в источнике — откуда?")

    penalty = sum(PENALTY[c] * len(v) for c, v in findings.items())
    score = max(0, round(100 - penalty * 100 / nw))
    result = {
        "words": len(W), "sentences": len(S), "avg_sentence_words": round(len(W) / max(len(S), 1), 1),
        "longest_sentence_words": longest, "paragraphs": len([p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]),
        "penalty_points": penalty, "score": score, "findings": findings, "fail": [],
    }
    if max_words and len(W) > max_words:
        result["fail"].append(f"длина {len(W)} слов > лимита {max_words}")
    if no_greeting and findings.get("greeting"):
        result["fail"].append("есть приветствие, а просили без")
    if source is not None and findings.get("foreign_number"):
        result["fail"].append(f"{len(findings['foreign_number'])} чисел не из источника")
    return result

LABELS = {"hard": "ЖЁСТКИЕ ЗАПРЕТЫ / следы нейросети", "parallel": "ОТРИЦАТЕЛЬНЫЙ ПАРАЛЛЕЛИЗМ (не просто X, а Y)", "calque": "КАЛЬКИ и лёгкие глаголы", "intro": "ВВОДНЫЕ и связки",
          "eval": "ОЦЕНКИ (заменить фактом)", "bureau": "КАНЦЕЛЯРИТ / отглагольное", "vague": "НЕОПРЕДЕЛЁННОЕ",
          "passive": "СТРАДАТЕЛЬНЫЙ ЗАЛОГ", "participle": "ПРИЧАСТИЯ", "transition": "ПРЕДЛОЖЕНИЕ НАЧИНАЕТСЯ СО СВЯЗКИ",
          "long_sentence": "ДЛИННЫЕ ПРЕДЛОЖЕНИЯ (>25 слов)", "dash_excess": "ТИРЕ", "triad_excess": "ПРАВИЛО ТРЁХ",
          "bold_excess": "ЖИРНЫЙ", "emoji_excess": "ЭМОДЗИ", "header_in_short": "ЗАГОЛОВКИ", "paren_excess": "СКОБКИ",
          "not_only": "НЕ ТОЛЬКО… НО И", "greeting": "ПРИВЕТСТВИЕ", "foreign_number": "ЧИСЛА НЕ ИЗ ИСТОЧНИКА", "english_prose": "АНГЛИЙСКАЯ ПРОЗА"}

def report(r, verbose=True):
    out = []
    out.append(f"слов {r['words']} · предложений {r['sentences']} · в среднем {r['avg_sentence_words']} слов/предл · самое длинное {r['longest_sentence_words']} · абзацев {r['paragraphs']}")
    for cat in PENALTY:
        hits = r["findings"].get(cat)
        if not hits: continue
        out.append(f"\n[{LABELS[cat]}] ×{len(hits)}  (−{PENALTY[cat]} за штуку)")
        if verbose:
            for h in hits[:12]:
                note = f"  ← {h['note']}" if h["note"] else ""
                out.append(f"  стр.{h['line']:>3}  «{h['hit']}»  {h['context']}{note}")
            if len(hits) > 12: out.append(f"  … ещё {len(hits)-12}")
    out.append(f"\nЧИСТОТА: {r['score']}/100   (штраф {r['penalty_points']} на {r['words']} слов)")
    for f in r["fail"]: out.append(f"FAIL: {f}")
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="файл с текстом или - для stdin")
    ap.add_argument("--source", help="файл с исходными данными: числа в тексте, которых нет в источнике, помечаются")
    ap.add_argument("--max-words", type=int)
    ap.add_argument("--no-greeting", action="store_true", help="приветствие в начале считать ошибкой")
    ap.add_argument("--min-score", type=int, help="exit 1 если ЧИСТОТА ниже")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="только счётчики и балл")
    a = ap.parse_args()
    text = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    source = open(a.source, encoding="utf-8").read() if a.source else None
    r = analyze(text, source=source, max_words=a.max_words, no_greeting=a.no_greeting)
    if a.min_score is not None and r["score"] < a.min_score:
        r["fail"].append(f"ЧИСТОТА {r['score']} < {a.min_score}")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(report(r, verbose=not a.quiet))
    sys.exit(1 if r["fail"] else 0)

if __name__ == "__main__":
    main()
