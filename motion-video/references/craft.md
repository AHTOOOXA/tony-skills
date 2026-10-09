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
7. Gotchas that cost a render
8. Seamless loops

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

**Beat punches** (CMD): a tiny scale kick on the beat makes a music-led film feel cut *to* the track, even
in shots where nothing else lands on the beat. `punch(t, beats, {bars, from})` in the template returns a
scale multiplier: +1.2 % per beat, +3 % per bar (downbeat), ~30 ms attack, exponential decay with a
~0.12 s time constant (gone well before the next beat at 120 BPM). Beat times come from `beats.py`
(`window.beats_in_film`, `downbeats_in_film`, `drop_in_film`) or `cues.json`, loaded in `__ready`.
- Build it up: beats only before the drop, bars join from the drop (`from: drop`) — the punch becomes the
  energy curve. A quiet intro or a breakdown gets none.
- Put it on the stage, titles, graphic layers — multiply it into the camera's scale, don't fight it.
- Not on footage holds or UI the viewer is reading (a pulsing sentence is harder to read and the rest stops
  being a rest): pass those spans as `quiet`, or keep that layer outside the punched container.
- Not with a voice-driven film unless the music is up front; not on a calm/luxe film; one punch system per
  film — punching the camera AND every title doubles it. Over ~5 % reads as a glitch, not a beat.

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
- Only where something moves > ~20 px/frame; unblurred motion > ~80 px/frame strobes (the eye sees
  separate copies, not a move). Any move faster than that outside a blur window is a bug: wrap it in a window,
  or slow it. `qa/check_video.py --blur a-b,…` flags whole-frame/band moves over 80 px/frame (on a 1080 canvas)
  outside the windows you pass; a small element flying alone isn't caught — look at those frames yourself.
  A cut-the-curve exit (in4, 230 px in 0.2 s) peaks near 150 px/frame instantaneously and steps 65–75 px
  between sampled frames at 30 fps — borderline, which is why the template blurs it. Longer or faster: always.
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

## 7. Gotchas that cost a render

Each of these shipped a broken frame for someone (twoclipping, CMD, onetake, our own runs):
- **z-index on every layer.** Without it a card floats over the flood that should cover it.
- **Declare everything before the first `__seek`.** A `let` read by `__seek` before it's set throws only in a
  worker that seeks frame 0 first.
- **No `will-change: transform` on anything the camera scales.** Chrome rasterises it once; zoomed-in text goes soft.
- **Hidden parent, visible child:** a child with `visibility: visible` shows through a hidden parent; use `inherit`.
- **Measure text after the camera scale is known** (`measureText` or `getBoundingClientRect` ÷ zoom), not before.
- **Images:** wait on `onload` (the template's `imagesLoaded()`), not dozens of concurrent `decode()` calls; a
  failed image must fail `__ready`, never ship as a blank.
- **A preview that cuts away and comes back is two cuts.** List both in `__meta.cuts`.
- **CSS animations are fine, transitions are not:** `render.mjs` seeks every CSS/Web Animation to t, but a
  transition depends on a state change, so it is disabled.


## 8. Seamless loops

A loop (a LinkedIn/X autoplay, a UI-morph reel, a background) is judged at the seam: viewers see it
three or four times, and the one hitch is what they notice. Set `__meta.loop = true` as a note to yourself
and to the checker; the renderer doesn't change.
- **Design for t ∈ [0, T).** The encoder's last frame is T − 1/fps, and "frame T" *is* frame 0. Draw the
  state at T equal to the state at 0, and the last frame is then one ordinary step before it. Drawing the
  end state on the last frame instead gives a duplicated frame — a hold that reads as a stutter.
- **Position AND velocity.** Matching where things are isn't enough: a spring that is still settling
  at T and starts from rest at 0 is a speed break. Repeat the cycle's changes one loop earlier
  (`track(t, base, loopKeys(changes, T))`) so the tails at 0 are the tails at T; easings ending at
  zero speed are fine on both sides of the seam.
- **Whole cycles.** Every periodic motion (a spin, a bob, a belt, a pulse, a gradient drift) runs a whole
  number of cycles over T: `cyc(t, period)` snaps the period to T/n. A 2.3 s bob in a 6 s loop jumps.
  Seeded noise loops if it is sampled on a circle (`sin/cos(2π t/T)` as its coordinates), not along t.
- **Music bars divide the loop.** T = whole bars (at 120 BPM a bar is 2 s: 4, 6, 8 s loops); the audio cut
  sits on a downbeat and its tail is mixed into its head (or the track is itself a loop), so sound has no
  seam either. Beat punches get `loop: T` so a tail crosses the seam.
- **No hold or fade at the seam.** A fade to black and back is the slideshow ending, not a loop; an end
  card held for 2 s kills the "is it over?" moment. The last beat sets up the first (CMD: "back to state 0").
- **One thing transforms** (A becomes B becomes … becomes A) works better than a sequence of scenes:
  5–9 s, one moving subject, the cut is invisible because nothing cuts.
- **Check:** `qa/check_video.py out.mp4 --loop` compares the seam step (last → frame 0) with its neighbours
  and the median step and names a JUMP, a HOLD or a SPEED BREAK. Then watch it twice in a row:
  `ffmpeg -stream_loop 2 -i out.mp4 -c copy loop3.mp4`.
