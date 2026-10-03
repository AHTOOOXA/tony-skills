# Layout, type and formats

## Safe areas (text, logos, faces)

Platform UI covers the frame: the right rail (likes, comments, share), the caption and CTA bar at the bottom,
the top bar. Combined TikTok + Reels safe area on **1080×1920: x 65–940, y 270–1248**. The template exposes
it as `SAFE`. Footage and a mascot's body may bleed outside; words may not.
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

9:16 first. Then 1:1 and 16:9 from the SAME timeline via the layout function (`?format=square|wide` in the
template) — reframe type and UI per format, never crop a 16:9 render to vertical. Frame 0 is the poster
(platforms ignore cover metadata): make the hook settled on frame 0 rather than swapping in a poster frame
that differs from frame 1 (that flashes).
