# Craft: moves and good defaults

A library, not a rulebook: techniques that made films feel expensive, with numbers that are good starting
points. Break any of them when the idea calls for it. Sources: claude-motion-design (CMD), onetake, brag,
HyperFrames (HF), ClaudeAnimationBase (CAB), our own renders (`tools.md`).

## Contents
1. Reads and rhythm
2. Easing and springs
3. Camera
4. Carries instead of cuts
5. Motion blur
6. The slop list (what makes it look AI-made)

## 1. Reads and rhythm

**Think in reads.** For every shot list what a first-time viewer must understand, in
order, with start/end times. You know what happens because you wrote the code; the viewer sees it once at
full speed. "One read at a time — when two things happen at once, the viewer sees only one." "Fast
actions, slow meanings": a move can be quick if anticipated; its meaning needs held time. Let the reads
set the length. (CAB: an ending packed into 1.3 s was unreadable; 4 s with 7 sequential reads worked.)

**Lead the eye** before an important read: the camera moves there, a character looks there, it lights up.

**Rhythm is what kills the slideshow feel** (onetake measured accepted vs rejected films):
- shot lengths vary: coefficient of variation ≥ 0.25 and range ≥ 4× (0.25 s words next to 2.5 s holds);
  the slowest scene ≥ 3× slower than the fastest (HF);
- ≥ 25 % of frames are rests (product footage holds dead still), with at least one ≥ 1 s;
- a burst somewhere: ≥ 3 big changes within 1.5 s;
- something new every 2–4 s; a visual payoff every 3–5 s; no hold > 1 s except rests and the end card;
- vary how shots end — the same exit twice in a row starts to feel like a template.

**Default short-form pacing from a model is too slow** (promptwarrior): give explicit cut rates.

**Timing table** (cross-source consensus):

| What | Duration |
|---|---|
| entrance | 0.3–0.6 s (fast in, then hold) |
| exit | faster than the entrance, ~0.25 s |
| urgent / standard / luxe move | 0.15–0.3 / 0.3–0.5 / 0.5–0.8 s |
| total stagger of a group | < 0.5 s, ordered by importance |
| word stagger | 40 ms hook · 80 ms conversational · 150 ms documentary |
| iris / flood | 0.30–0.35 s, must clear the farthest corner |
| zoom-to-target | 1–2 s for 1.6–2× (under 0.8 s reads as a teleport) |
| a screen of a real app | 1.0–1.5 s minimum on screen |
| end card | held ≥ 1.5–2.5 s settled, to the last frame |

## 2. Easing and springs

Linear motion reads mechanical. Pick the curve by **t80** (fraction of the duration where 80 % of travel is done):
linear .80 · smoothstep .71 · cubicOut .42 · quintOut .28 · expoOut .23. **Vary them** — one S-curve on
every move got a film rejected as "all the same".

Closed-form springs (no simulation, so any frame renders alone) — `spring()` / `track()` in the template:

| Preset (stiffness/damping) | f, z (template) | Use |
|---|---|---|
| 320/30 | 4.0, .84 | snappy UI, presses |
| 170/26 | 2.6, .80 | containers, cards, camera |
| 120/24 | 2.0, .85 | heavy type, logos |
| 180/12 | 2.6, .45 | mascot and stickers ONLY (visible overshoot) |

Overshoot as a dial: UI ~3 %, type little or none, camera usually none; a mascot or a sticker can bounce.
One playful element reads as charm; everything bouncing reads as cartoon — unless cartoon is the idea.
Overshoot applies to transforms, never opacity. A value with several targets is a SUM of springs (`track`).
Text that swaps: exit ~120 ms, enter 60 ms later on its own spring, never overlapping.
Easings must return exactly 0 and 1 at the ends (a 1e-9 residue made an element appear 2 s early).

## 3. Camera

- One transform on a container, keyed `[t, zoom, x, y]`; **interpolate zoom in log space**.
- One move per scene reads calm and intentional; zooming in then straight back out reads indecisive;
  a springy camera usually feels cheap.
- Follow: key the subject ~0.1 s ahead (sineInOut). Snap: key the landing before the subject arrives (expoInOut).
- Zoom-to-target: target fills ≤ 88 % of the frame; the raster source must be ≥ zoom × rendered size
  (capture UI at deviceScaleFactor 2–2.5 so a 1.2–1.5× push stays sharp).
- **Use the push for legibility**: zoom into the one sentence/number that is the payoff so it reads at phone
  size (on-screen UI text ≥ 26 px = font × capture scale × zoom). Keep the column inside the frame.
- Rests: product footage dead still; a stage (sky, props, mascot) may breathe.
- No shake in UI films (at 30 fps with a 180° shutter it doubles every letter).

## 4. Carries (and when to cut)

A film reads as slides when beats *replace* each other with nothing surviving. At every boundary something must survive and move
≥ 2 % of the frame diagonal or scale ≥ 10 % (onetake's carry score; < 0.5 = slideshow). Hard cuts are a tool too —
on the beat, in a burst, into the end card. The cause must be visible (a finger, a cursor) — a page reacting to
nothing reads as a screensaver.

| Carry | Recipe |
|---|---|
| **Iris from the subject** | circle grows from the character/object, clears the far corner in 0.33 s (out3); closes on the way out (in3) into where the next thing appears |
| **Shared element** | the thing pressed becomes the result; a clock flies down and lands as a label; a bubble becomes a card |
| **Cut-the-curve slide** | exit accelerates (in4, 0.2 s, −230 px), hard swap, entry decelerates (out3, 0.28 s, +230 px). **No fade, no scale** — fading both sides dips to dark |
| **Zoom-through** | exit 1→1.2 on power3.in 0.2 s, hard swap, entry 0.75→1 on expo.out 0.5 s |
| **Match on action** | cut at peak velocity, same direction and speed |
| Usually weaker | crossfades between busy layouts (mud), blur-ins, gratuitous 3D flips, default particles, glow on UI chrome |

A sticker/label over footage: pop in AFTER the slide lands, leave BEFORE the next slide (never ride a blur
window). Land carried elements on empty art, not on text or faces. Every screen needs its own placement pass:
footage scrolls under fixed overlays.

## 5. Motion blur

`render.mjs` does it from `__meta.blur` windows: SUB sub-frames (10) spread over a 180° shutter, averaged in
**linear light**, never across `__meta.cuts`.
- Only where something moves > ~20 px/frame; unblurred motion > ~80 px/frame strobes.
- 4 sub-frames leave ghost copies; 8–10 is enough.
- A layer that must stay sharp inside a blur window (text in flight) uses frame-quantised time `quant(t)`.
- Never average across a hard swap: two layouts dissolve into mud. List the swap in `cuts`.
- CSS `blur()` is not motion blur.

## 6. The slop look

What reads as generic AI output (0xMovez, 1littlecoder, CMD critic): centred title on a gradient, everything fading in,
a logo at the end, uniform shot lengths, corner labels and frame borders, particle bursts, glow on UI,
emoji, rainbow gradients, an "Innovative AI assistant" headline, a moral in the last frame. Fix with a
named reference ("Apple keynote product film", a URL): extract frames every 0.5 s, write `style_guide.md`
(palette, type, shot lengths, transitions, camera, how text enters/exits) — take the grammar, never the content.
