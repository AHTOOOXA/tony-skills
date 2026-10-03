# QA and the critique loop

Look at frames; don't just generate them. Every check below is a command.

## Commands

```bash
node scripts/render.mjs comp.html --stills 0,1.6,3.3,8 -o stills/     # 4 stills before anything else
bash scripts/qa/sheets.sh out.mp4                                      # sheet.png (2 fps), phone.png (360 px), strips
python3 scripts/qa/check_video.py out.mp4 [--cuts 3.8,14.2]            # tags, pops, flashes, frozen spans, rhythm
uv run --with librosa --with pyloudnorm --with soundfile --with scipy python scripts/qa/verify_audio.py sound.json
```

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
at fps=2, a phone sheet at fps=1 scale=360, frame 0, 12-frame strips around <fast moments>) and look at them.
Report only: 1) what you understood the film says, in one sentence; 2) things that are broken or unreadable
(flashes, pops, cut-off or covered text, ghosting, unreadable sizes, anything off-brand vs <assets>), each with
a timestamp and a concrete fix. Don't critique the concept or the taste. READ-ONLY.
```
