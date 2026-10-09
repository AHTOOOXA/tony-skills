---
name: motion-video
description: Make motion-design videos as code — app showcases, product launch films, promo reels, explainers, brand/rebrand reveals, logo animations, animated ads for TikTok/Reels/Shorts/Telegram/X — rendered frame by frame from HTML (Playwright + ffmpeg), with real captured UI, music-led editing, sound design and quick visual checks. Use it whenever the user wants a video, ролик, promo, reel, teaser, motion graphics, "анимацию для соцсетей", a launch or showcase video of their app or site, a logo/rebrand animation, or to improve an existing rendered video — even if they don't say "motion design" or name a tool. Not for: editing camera footage in an NLE, image→video model generation only, or static images.
---

# motion-video

You are the motion designer and the director. You write the film as a program — an HTML page whose
`__seek(t)` paints the frame for time `t` — and this skill gives you a studio: a renderer that encodes it
properly, a recorder for real apps, a sound and music mixer, analysis tools, and a library of what has
worked for others. Use what helps. The film is yours.

**Go all out.** The videos people share come from one strong idea executed with conviction — a baguette
launched like an iPhone, a logo that becomes the whole film, a mascot's tiny love story with the app at the
end — not from following a checklist. Pick the idea first; let craft serve it.

If `~/.claude/motion-video/house-rules.md` exists, read it: it's the owner's short list of things that
went wrong for them before (e.g. fake UI). Respect it; it's not a style guide.

## How to work

1. **Find the idea.** What does this film *claim*, and what's the one picture that proves it? Know the
   typical film for this kind of job (a rebrand's is "logo → palette → type → end card"; an app's is
   "hero → 3 features → CTA") and beat it. `references/concept.md` is a toolkit for this — story, idea
   generators, how to pick, tests that catch a tour; `references/inspiration.md` shows what landed and how
   it was asked for, and how to pull a reference prompt from the public galleries. Pick the look on purpose:
   `references/styles.md` has a card per style with checkable signature features. Use the brand's own material boldly. If the direction is genuinely the user's call,
   show contrasting ideas in a line each; otherwise commit to the strongest.
2. **Pick the drive.** Music usually drives the cut: choose a track (or none, deliberately), analyse its
   beats (`scripts/beats.py`) and hang the big moments on downbeats and the drop. Or drive by voice
   (`scripts/vo.py` → word times; `references/voice.md`), or by a single continuous camera move. Keep the
   times in one `cues.json` that both the comp and `mix.py` read.
3. **Build** from `templates/compose.html` — it has springs, easings, masked text, iris, slides, a log-zoom
   camera, footage playback, a safe-area box, a format switch and `loadJSON`/`word()` for cue and word times.
   Drawn looks (ink, boil, draw-on) get `templates/drawn.js` (example: `drawn-demo.html`). Real product? Record it with
   `scripts/capture.mjs`. Brand assets? Use the real SVGs and fonts.
4. **Look early, look often.** Render stills (`--stills`) and a quick draft (`--draft`) and actually look
   at them (`qa/sheets.sh` → Read the PNGs). Your code always looks right to you; the frames tell the truth.
5. **Polish and ship.** Full render, sound (`scripts/mix.py`), a fast technical pass (`qa/check_video.py`,
   `qa/verify_audio.py`). If you want fresh eyes, ask a separate agent what it sees and what's broken —
   bugs and readability, not a vote on your idea. Deliver the MP4 and say what nobody has heard yet.

## The studio

```bash
S=<this skill dir>
node $S/scripts/render.mjs comp.html --stills 0,1.6,3.3 -o stills/     # look at key frames
node $S/scripts/render.mjs comp.html --draft -o draft.mp4              # half size, fast — judge the rhythm
node $S/scripts/render.mjs comp.html -o out.mp4 [--audio mix.wav] [--fps 60] [--ss 2] [--workers 4] [--keep-frames]
node $S/scripts/render.mjs comp.html -o out.mp4 --range 4.2,6         # re-render one span into kept frames
uv run --with numpy --with soundfile python $S/scripts/vo.py all s1.wav s2.wav --script script.txt -o vo.wav  # tidy + words/captions/cues.json
uv run --with numpy --with soundfile python $S/scripts/vo.py check final.mp4 script.txt                      # narration vs the script
uv run --with librosa python $S/scripts/beats.py track.mp3 [--len 15]  # beats, downbeats, drop, best window
uv run --with librosa --with pedalboard --with pyloudnorm --with soundfile python $S/scripts/mix.py sound.json --video out.mp4 --mux final.mp4
bash $S/scripts/qa/sheets.sh out.mp4 [t…]                              # sheet / phone-size / frame 0 / strips
python3 $S/scripts/qa/check_video.py out.mp4                           # colour tags, flashes, frozen spans, rhythm
uv run --with librosa --with pyloudnorm --with soundfile --with scipy --with pedalboard python $S/scripts/qa/verify_audio.py sound.json
```
Needs node, ffmpeg, uv, and Playwright resolvable from the working dir (`npm i -D playwright`, or run from
a project that has it). System Chrome is used when present.

What the tools already do for you (so you don't have to think about it): PNG frames encoded as
limited-range BT.709 with correct tags; motion blur from sub-frames in linear light on the spans you mark
(`__meta.blur`), never blended across a hard cut (`__meta.cuts`); fixed grain against banding on dark
gradients; parallel rendering; CSS animations seeked to t; page errors and failed fonts/images reported;
real-app capture on a slowed clock at device pixels; sounds placed on their
measured peak, levelled by perceived loudness, mixed in one room, music ducked under a voice, mastered for social.

## The composition contract

```js
window.__meta  = { duration, fps, width, height, blur: [[t0, t1], …], cuts: [t, …] };
window.__seek  = t => { /* paint frame t — derive everything from t */ };
window.__ready = Promise; // fonts and images decoded
```
Everything is a function of `t` (no timers, no CSS transitions, seeded randomness) so any frame renders
alone and in parallel. That's the only hard rule — it's what makes the renderer work.

## Where to look

| When you want… | Read |
|---|---|
| finding the idea: claim, tension, idea generators, picking, anti-tour tests | `references/concept.md` |
| ideas that worked, real prompts, what made them land; pulling a reference from the galleries | `references/inspiration.md` |
| a style per film: cards with signature features, routes, traps (drawn, graphic, editorial, FX, 3D) | `references/styles.md` |
| moves: timing, springs, camera, transitions/carries, blur, rhythm, gotchas | `references/craft.md` |
| vertical layout, safe areas, type sizes, formats | `references/layout.md` |
| story, hooks, copy, mascots and characters | `references/story.md` |
| recording a real app or site | `references/capture.md` |
| music, sound design, the mixer, free/licensed sources | `references/sound.md` |
| voice-driven films: narration as the clock, word times, captions, ducking, STT check | `references/voice.md` |
| checks and getting fresh eyes | `references/qa.md` |
| other skills/frameworks (Remotion, HyperFrames, brag, onetake…), licences | `references/tools.md` |
