# Layout, type and formats

## Safe areas (text, logos, faces)

Platform UI covers the frame: the right rail (likes, comments, share), the caption and CTA bar at the bottom,
the top bar. Combined TikTok + Reels safe area on **1080×1920: x 65–940, y 270–1248**. The template exposes
it as `SAFE` (per format: see the table under Formats). Footage and a mascot's body may bleed outside; words may not.
(Meta Reels ads guide: keep 14 % top, 35 % bottom, 6 % sides free. TikTok: depends on caption length;
third-party ad specs give ~130 px top, 484 px bottom, 140 px right.) HyperFrames' looser box:
x 108–972, y 192–1728, nothing important below y ≈ 1600.

A label that must sit over moving footage needs its own placement per screen: find the empty strip
(card art, gaps between widgets), keep it inside the safe area, check it against what scrolls under it.

## Type sizes (1080-wide canvas)

| Element | Size |
|---|---|
| hook / headline | 90–132 px (one line where possible) |
| overlay body, labels on stickers | ≥ 56–64 px |
| small label | ≥ 46 px (never under 32) |
| CTA / URL on the end card | ≥ 52 px, full-contrast colour, not grey |
| app UI text on screen | ≥ 26 px = font × capture scale × zoom |

Test at phone size: `qa/sheets.sh v.mp4` writes `phone.png` (frames at 360 px wide, 1/3 scale).
Text width ≈ px × characters × 0.55. Use the product's own fonts; check the script subset (Cyrillic etc.):
many display fonts have none and the browser silently falls back. Load webfonts with sample text if the
subset is lazy (`document.fonts.load('700 100px "Caveat"', 'ЗВЕЗДА')`).
On dark grounds: one weight lighter, +0.05–0.1 line-height. Counters: `tabular-nums`. Don't animate
letter-spacing, weight or blur on words (reflow jumps); don't fade both a container and its words.

## Reading floor

5–10 words/s (low end for languages with long words); a 1–3-word label ≥ 0.8 s settled; a sentence 0.3 s/word,
min 1.2 s, counted from when the whole line is visible. "Fast in, then hold." Captions ≥ 0.5–0.7 s,
≤ 17 chars/s, ≤ 2 lines.

## Colour

3 colours, one accent used only for active states. No pure black or white grounds. Dark gradients band in
8-bit: `render.mjs --grain 3` adds a static luma noise at encode (never animate grain). Frames are encoded as
limited-range BT.709 with correct tags — don't re-encode with a plain `ffmpeg -i frames -c:v libx264`
(BT.601, full range: reds and purples shift, blacks lift).

## Formats

9:16 first. Then 4:5, 1:1 and 16:9 from the SAME timeline via the layout function (`?format=portrait|square|wide`
in the template) — reframe type and UI per format, never crop a 16:9 render to vertical. Frame 0 is the poster
(platforms ignore cover metadata): make the hook settled on frame 0 rather than swapping in a poster frame
that differs from frame 1 (that flashes).

| Format | Size | Where | Safe area for words (`SAFE`) |
|---|---|---|---|
| `vertical` 9:16 | 1080×1920 | TikTok, Reels, Shorts, Stories | x 65–940, y 270–1248 (above) |
| `portrait` 4:5 | 1080×1350 | Instagram/Facebook feed, LinkedIn and X feeds on mobile — the tallest a feed shows uncropped | x 108–972, y 135–1215 |
| `square` 1:1 | 1080×1080 | feeds, Telegram | 6 % sides, 8 % top, 14 % bottom |
| `wide` 16:9 | 1920×1080 | YouTube, X/LinkedIn desktop, landing pages | same rule |

**4:5 notes.** Meta's feed guidance is "keep text and CTAs in the central 80 %" — 10 % margins, the box above
(third-party ad-spec sites, not Meta's own page: unverified). The Instagram profile grid shows 3:4 tiles
(since Jan 2025), which trims a 4:5 frame by ~34 px on each side — inside the margins already. A 4:5 video
that also runs as a Reel is shown in the 9:16 player with the Reels UI over its lower part, so keep the
words above ~y 1000 if it doubles as one (unverified; check a test post). LinkedIn's video player overlays
nothing big in-feed, but the caption sits below — the first frame still has to read as the poster.

## Languages: one composition, many cuts

`?lang=ru` in the template, every string through `tr(key)` from one `STRINGS` table. Never fork the file per
language: every later motion fix would be made twice, and the cuts drift apart. (onetake: the source language
must stay pixel-identical after the table is added — render a few stills before and after and compare.)
- **Write each language, don't translate.** Its own word order and length for about the same seconds; a line
  that names a UI label uses the label the localised UI actually shows. Wordplay rarely survives: write a
  new line rather than explain the old one.
- **Lengths differ by ~±30 %** (German and Russian run long, Chinese/Japanese short but need bigger type):
  line breaks live per language in the table, and every language gets its own layout pass —
  `checkSafe('#hook', …)` in `__ready` logs any element whose words leave the safe area; then look at
  `--stills` per language and format. Shrink type only down to the floors above; past that, cut words.
- **Fonts per script.** The display face may have no Cyrillic/Greek/CJK (the browser falls back silently):
  load a matching face for that language only and put it second in the stack, so Latin keeps the house face.
- **Timing per language from files, not from the comp.** A voice in another language has its own pauses and
  word order: generate its `words.json`/`cues.json` with `vo.py` (`cues.${LANG}.json` in `__ready`) and key
  beats to *words that mean the same thing* (`word(words, 'бесплатно')`), not to the source's seconds. Where
  one language talks longer before a payoff, start the payoff earlier in its sentence instead of slowing the
  move (a move played at < ~0.5× or > ~1.4× its authored speed looks wrong).
- **Match loudness per language as the last step.** A denser voice mastered to the same peak came out 5 LU
  louder than the source cut (onetake). Measure each language's final mix (`check_video.py` prints integrated
  LUFS) and bring them within ~1 LU of each other.
- Dates, numbers and currency follow the locale (9 октября, 1 290 ₽ with a thin no-break space); switching a
  symbol without converting the number is a different claim — ask.
