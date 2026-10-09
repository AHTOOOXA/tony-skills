# QA and the critique loop

Look at frames; don't just generate them. Every check below is a command.

## Commands

```bash
node scripts/render.mjs comp.html --stills 0,1.6,3.3,8 -o stills/     # 4 stills before anything else
bash scripts/qa/sheets.sh out.mp4                                      # sheet.png (2 fps), phone.png (360 px), strips
python3 scripts/qa/check_video.py out.mp4 [--cuts 3.8,14.2]            # tags, pops, flashes, frozen spans, rhythm
uv run --with librosa --with pyloudnorm --with soundfile --with scipy --with pedalboard python scripts/qa/verify_audio.py sound.json
node scripts/render.mjs comp.html -o out.mp4 --keep-frames             # keep frames, then fix a span cheaply:
node scripts/render.mjs comp.html -o out.mp4 --range 4.2,6            # re-render 4.2–6 s only, re-encode
```

`render.mjs` also prints page errors, console errors and failed requests once each. A "request failed" for a
font or image means the film is rendering with a fallback: fix it before looking at anything else.

`check_video.py` reports: colour tags (must be BT.709 limited), duration/fps, single-frame flashes
(frame n differs from both neighbours while n−1 ≈ n+1), pops (a frame diff > 3× its neighbours and not a
declared cut), frozen spans > 2 s (nothing moves), and rhythm: share of still frames (≥ 25 % is healthy for a
product film) and a shot-length variation estimate.

## Fresh eyes (optional)

Your own frames always look right to you. A separate read-only agent looking at the MP4 finds the bugs you
can't see: a flash on frame 0, a label covering the payoff, two shots blended into mud, text cut at the edge,
a ghosted moving title, a CTA too small to read on a phone. Ask it for **what's broken and what doesn't read**,
with timestamps and concrete fixes — not for scores on taste, and not to redesign the idea. Committees
sand films down into safe, bland ones; keep the idea, fix the bugs.

Prompt:
```
Look at <video> (<N> s, <format>) as a first-time viewer on a phone. Extract frames yourself (ffmpeg: a sheet
at fps=2, a phone sheet at fps=1 scale=360, frame 0, 12-frame strips around <fast moments>, and full-resolution
frames at 5–8 key times — check edges, aliasing, banding, missing glyphs/fallback fonts there) and look at them.
Report only: 1) what you understood the film says, in one sentence; 2) things that are broken or unreadable
(flashes, pops, cut-off or covered text, ghosting, unreadable sizes, anything off-brand vs <assets>);
3) anything that reads as a generic AI template (references/craft.md §6); 4) if a style card was used
(<card>), each signature feature that is missing or wrong. Each item: timestamp, what you see, a concrete fix
with numbers (curve, frames, px, colour). Order by impact on the viewer, biggest first. Don't critique the
concept or the taste. READ-ONLY.
```

## Applying a review

- Keep the current render and source as version N before touching anything.
- Fix everything that's broken; for the rest, take what serves the idea and say what you skipped and why.
- Don't regress what already works. Re-render the affected spans (`--range`), re-run the checks, look again.

**A push round, only when the owner asks for more:** one more pass whose single goal is the strongest moment —
a bigger hero, a better carry, sound that lands harder — within the same idea, not a new one.

Why no 1–10 scores: an AI jury's scores cluster (mg-styles-15's finals sit between 7.57 and 8.21, four at
exactly 7.64), it can't hear the sound it grades, and a film that passes every rule can still be the bland
one. Ask for evidence and fixes, not a number.
