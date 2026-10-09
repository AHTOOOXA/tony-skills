# Styles: a card per look

A library, not a rulebook. Each card lists what a style is for, the signature features an expert checks
for, a route that works in this skill's renderer, what goes wrong, and the sound that fits. The numbers are
good starting points. Most come from the prompts **and the source code** of mg-styles-15 (15 films, one per
style, made by Opus writing code, MIT). Where the code disagrees with its own prompt, the card says so;
`(inferred)` marks anything we added ourselves.

## Contents
1. Picking and locking a style
2. Drawn family: frame-by-frame / cel + boil · line art · brush ink + watercolour · textured editorial
3. Graphic: flat vector · shape morph · geometric Bauhaus · isometric 2.5D · faceted low-poly
4. Editorial: sticker explainer · collage / cut-out · kinetic captions (9:16)
5. Light and FX: cyberpunk HUD / FUI · synthwave / VHS · aurora + glass · liquid
6. Retro and 3D: pixel art · 3D render (Blender)
7. Checking a film against its card
8. Sources and licences

## 1. Picking and locking a style

- **Picking a style is a decision, not a garnish.** Choose it for the claim: line art for precision and
  luxury, cel boil for hand-made warmth, HUD for "a system is working", aurora glass for calm AI products.
- **Name the medium concretely**: "black ink on cream paper, animated on twos", "paper cut-out under a
  rostrum camera", "pencil on parchment". A physical medium tells you the texture, the frame rate and the
  imperfections; "hand-drawn style" tells you nothing.
- **Once a style is chosen, its signature features beat the generic defaults in `craft.md`.** Flat vector
  bounces everything (craft.md keeps overshoot for mascots). Cel holds drawings with no motion blur.
  Bauhaus has no overshoot at all. Aurora glass has nothing fast. Pixel art never eases a sprite. When a
  default and a card conflict, the card wins. When two cards conflict inside one film, it reads as a
  mistake: pick one style per film, or make the switch the idea (a style relay).
- **Lock a series' look with numbers**: palette as hex, line weight in px, exposure (twos or ones), boil
  amplitude and rate, easing curves, grain %. Write them at the top of the comp or in `style_guide.md`.
  A remake reproduces only what was pinned with numbers; adjectives drift between sessions. Reuse one
  drawing engine across a series (`templates/drawn.js` for the drawn family).

## 2. Drawn family

`templates/drawn.js` gives you the drawn family's mechanics as pure functions:
- `expose(t, sched)` is the exposure sheet;
- `boil(pts, {seed, id})` makes the line boil;
- `inkStroke` is a tapered brush; `fillShape` lays off-register colour;
- `drawOn` and `paced` draw a line on with a glowing tip, paced by corners.

`templates/drawn-demo.html` shows them together.

### Frame-by-frame / cel animation + line boil
**For:** hand-made warmth, playful brands, explainers that should feel crafted rather than templated (the Buck / Giant Ant hybrid: clean shapes plus hand-drawn cel FX).
**Signature features:**
- **Exposure at 24 fps:** most drawings are held on 2s (12 drawings/s), fast action on 1s, and holds on 3s. The demo's sheet: `[0–8 f, 2s] [8–24, 1s] [24–48, 2s] [48–60, 1s] … [108–120, 3s] … [230–240, 3s]`. The camera stays on 1s even when the drawings are on 2s: pass the exposure time to the drawing and raw `t` to the camera.
- **Boil:**
  - 3–4 slightly different drawings cycle, a new one every 2 frames (3 drawings on a 3s hold).
  - The jitter is a world-space simplex field: amplitude 2.2–2.4 px, scale 70 px, re-rolled per drawing.
  - Seed it from a stable name (`"hero/body"`), never from the frame index.
  - Boil is a meaning (alive, nervous, hand-made). It is not a default: decide it per film.
- **Ink:** tapered strokes 4–6.5 px with pressure noise ±35 %. Tips thin to 25 % over ~10–14 px at the start and 20–26 px at the end. The stroke is heavier on the shadow side (+35 %). Straight edges overshoot their corners by ~3–10 px.
- **Colour:** fills are boiled on their own seed and printed off-register by (−5, +4) px, like hand colouring. Use a palette of 3–4 colours, e.g. ink `#1c1613`, tomato `#e5402b`, sun `#ffc425`, cream `#f4e9d0`.
- **Smear frame:** in a fast move, one frame stretches the object 150–300 % along its path. It appears on 1s, for one frame only (the demo also uses a frame of multiples).
- **Cel FX layer:** smoke puffs, sparks, star bursts, speed lines, drawn over the clean animation. Pops are frame-stepped, e.g. scale 0 → .55 → 1.35 → 1.1 → 1, one value per frame (our `drawn-demo.html`).
- **Paper:** a grain texture multiplied at 10–15 % over everything. In the demo the tooth texture is offset per drawing, so every cel is a new sheet.

**Route:** Canvas 2D. A centreline is resampled at ~3 px, boiled, then its pressure profile is turned into an outline polygon and filled. `drawn.js` does this.

**Traps:**
- Sub-frame motion blur on held drawings: leave them out of `__meta.blur`.
- The boil seed taken from the frame number: it jitters on every frame, and a re-render differs.
- Everything on 1s looks like vector tweening with noise.
- Boil amplitude above ~3 px reads as shaking.
- A close-up scales the boil and the pen weight up with it: divide both by the zoom (the demo's `GLOBAL.ink/amp`).
- Frame 0 is empty because everything pops in: open on something already drawn, or mid-action.

**Sound:** playful jazzy pizzicato or xylophone; cartoon SFX (strike, fwoosh, pop, poof, sparkle) on the exact frame. hanif: put each SFX ~0.03 s before contact.

**Source:** mg-styles `prompts/05-cel-boil.md`, `demos/05-cel-boil/js/engine.js` (boil, `inkW`, `outline`, `fillShape`), `scene.js` (`SCHED`, `REG`, smear frames); hanif `references/motion.md` (exposure, boil as a choice).

### Line art (one continuous line)
**For:** luxury, architecture, finance and logo films; anything that should feel precise and quiet.

**Signature features:**
- **Line:** one line of constant weight (2–4 px; the demo uses ~3 px) with round caps, in one or two colours on lots of negative space. Demo palette: midnight `#0B1320` with champagne gold `#E9D7A5`.
- **One-stroke narrative:** the tail of each figure is the start of the next (seed → sapling → building → skyline → horizon → monogram).
- **Draw-on:**
  - Use `stroke-dashoffset` / trim paths, or `drawOn`.
  - The signature ease is `cubic-bezier(.65,0,.35,1)`.
  - Time ∝ corner-weighted length: `dτ = ds·(1 + 9·min(curvature, 0.3 rad/px))`, curvature smoothed over ~7 px. `paced()` in `drawn.js` does this.
  - Punctuation holds of ~0.15 s sit on the music grid. The demo retimes the line so anchors land on a 72 BPM 1/8-note grid (`tools/retime.py`).
- **Pen tip:** a hot ~3 px core, a 15 px glow and a faint 56 px halo. The camera leads the tip: a Gaussian-weighted average of tip positions (σ 0.3 s) aimed 0.08 s ahead.
- **Trail:** older segments dim to ~35–40 % over 0.2–1.5 s of age. Blend toward a darker colour rather than alpha, so chunk overlaps stay invisible.
- **Line to fill:** after the outline closes, the same path fills from its anchor. In the demo the fill swells over ~0.23 s, and the bloom peaks one frame after the onset.
- **End:** the camera dollies out to reveal the whole drawing composed as a poster.

**Route:**
- **Canvas 2D:** a resampled polyline drawn up to `s(t)`, plus a glow pass (screen blend: blur 16 px at 0.2 and blur 3 px at 0.3).
- **SVG:** `getTotalLength()` + `stroke-dashoffset` works for simple pieces.

**Traps:**
- Constant pen speed through corners reads mechanical.
- Line weight that scales with the camera zoom: divide `lineWidth` by the zoom.
- Thin lines shimmer at 1× scale: supersample (`--ss 2`).
- Figures joined by visible jumps break the one-line promise.

**Sound:** minimal felt piano and a soft string swell. A pen-on-paper whisper whose loudness follows tip speed. A delicate chime on the fill.

**Source:** mg-styles `prompts/02-line-art.md`, `demos/02-line-art/film.js` (corner density, camera, tip, trail), `tools/retime.py`.

### Brush ink + watercolour
**For:** warm hand-lettered explainers and history recaps; lively, a little imperfect.
**Signature features:**
- Fibre paper.
- Tapered brush strokes, 4–6 px, that boil at ~10 fps.
- Watercolour washes that bloom from a point: multiplied, with a pooled edge and granulation.
- Lettering that writes itself.
- Things draw on, then act; exits pop out or get whipped away by the camera.
- Palette: cream, ink `#2A2420`, one accent red `#D0312D`, soft greens/blues/yellows as washes.
- Dark chapters: a multiply radial darkens the plate, with one light glowing through.

**Route:** Canvas 2D, `inkStroke` + `boil` on a 10 fps clock (`id = floor(t·10)`); washes are multiplied polygons that grow from a seed point (inferred, for this skill; hanif's `pen.wash`).

**Traps:**
- Multiply washes on a dark shape go muddy: paint opaque on dark.
- Smoothing short polygons turns a 4-point tower into a blob: keep corners sharp.

**Sound:** a soft bed, foley per contact; no continuous pencil-scratch bed. hanif tested one and rejected it because it fights everything.

**Source:** hanif `references/styles.md` § 2, `traps.md`.

### Textured editorial (storybook)
**For:** calm, precise, tactile science or story illustration.

**Signature features:**
- **Paper:** `#F3EEDD` + grain. Diagonal light bands; film finish with grain flicker ±2.5 % and vignette 0.18.
- **Ink:** `#1E1612`, 2.6–3.4 px, round joins.
- **Motion:** no boil on still shots (they hold perfectly still); acting on twos.
- **Texture:** every surface has three layers, base → texture → edge.
- **Construction guides:** blue `#5E80CC` (circles with `+` centres, dashed spirals, rulers) as a device for growth and geometry.
- **Format:** 24 fps, square 1080.

**Route:** Canvas 2D; hatching clipped to shapes (`hatch` in 05-cel-boil `engine.js`: gap 11–14 px, angle ±1 rad).

**Traps:** a flat fill reads unfinished; blob characters (build rigs with anatomy).

**Sound:** a quiet bed; SFX from the timeline.

**Source:** hanif `references/styles.md` § 1, `SKILL.md` hard rules.

## 3. Graphic

### Flat vector
**For:** the mainstream explainer and SaaS look (Google Material, Motion Ocean): product promos, annual reports, science explainers.

**Signature features:**
- **Look:** flat colour blocks, no gradients (or nearly none), no outline or a minimal one, geometric characters with limb rigs rotating on anchors, clean negative space.
- **Palette:** a saturated 5–6 colour set, e.g. ultramarine `#2B2BFF`, coral `#FF5A4E`, sunflower `#FFC62B`, mint `#2EE6A8`, cream `#FFF6E9`, ink `#151433`, plus one darker shade per colour for flat side faces.
- **Elastic everything:** anticipation → stretch → squash → overshoot → settle.
  - The prompt says `cubic-bezier(.34,1.56,.64,1)`. The demo defines it but actually uses a closed-form damped spring (f 2.4 Hz, ζ .42), with the residual pinned to exactly 1 after 0.9 s so nothing drifts under zoom.
  - Squash/stretch is driven by spring velocity, clamped ±30 %: ~20 % on buildings in the demo against the prompt's ~10 %.
  - A falling ball stretches 16 %; the first impact squashes to 0.60 × 1.36 over 3 frames.
- **Stagger:** 2–4 frames (clouds 5 f, birds 3 f, logo dots 1 f). One hero moves at a time.
- **Transitions:** a shape wipe (a bubble scales 1.12 → 34× over 10 f, then 9 f colour wipes) or an element flying out and carrying the cut.
- **Format:** 30 fps.

**Route:** SVG or Canvas, closed-form springs (`spring()` in compose.html with f 2.3–2.8, ζ .38–.5). Keep wipe edges hard inside blur windows: the demo's `crisp()` gives wipe edges only 8 % of the shutter.

**Traps:**
- Gradients and drop shadows creep in.
- Several heroes move at once.
- Uniform stagger reads as a template.
- The same overshoot on everything (vary f and ζ per element class).

**Sound:** upbeat future bass or pop ~120 BPM; pop, boing and whoosh on each entry, frame-synced.

**Source:** mg-styles `prompts/01-flat-vector.md`, `demos/01-flat-vector/index.html`.

### Shape morph
**For:** visual storytelling in one shape (a cup becomes a sunset becomes a pin); Apple-keynote-grade explainers.

**Signature features:**
- **Continuous outline:** no jumps, 6–8 meaningful shapes per 10 s, on the beat.
- **Bridge:** a complex A→B goes through a simple intermediate (a circle, r ~100–120 px in the demo). Each half (A→○, ○→B) takes 8–12 frames.
- **Ease:** `cubic-bezier(.7,0,.3,1)`, fastest mid-way. The demo applies it to each half separately, so the shape also cushions at the circle; the prompt's "3-frame cushions" come from the curve, not from holds.
- **Squash and stretch:** 10–15 % along travel, `k = 1 + sq·sin(πg)` with sq 0.05–0.14, plus rotation of −26° to +24° mid-morph.
- **Impact:** a damped-sine squash (A 0.07–0.26, period 0.28 s) starting 2 frames before the hit.
- **Sub-parts morph in sync** (steam → rays → waves) with ~0.03 offsets. Strokes with no target shrink to their midpoint before the circle.
- **Background:** a colour field per shape, changed by a circular clip growing from the morph origin over 0.55–0.6 s, edge feathered by speed × shutter.

**Route:** SVG/Canvas. The prompt suggests flubber or MorphSVG; the demo instead resamples every shape to 240 equal-arc points, orients them CCW, and brute-forces the cyclic shift with the least squared distance. That is the "first vertex" fix.

**Traps:**
- Knotting or self-crossing mid-morph: check a still at every midpoint.
- Different vertex counts.
- A→B without the bridge (mush).
- A morph without rotation or squash looks like interpolation.

**Sound:** a rhythmic plucky arpeggio; a pitched whoosh per morph landing on the beat.

**Source:** mg-styles `prompts/08-morph.md`, `demos/08-morph/index.html`.

### Geometric Bauhaus (kinetic poster)
**For:** music-driven posters, identities, anything rational and rhythmic.

**Signature features:**
- **Palette:** primaries plus black and white only: cream `#F1E9DA`, red `#E03C31`, yellow `#F2B705`, blue `#1E4FA3`, black `#111`.
- **Grid:** a strict module (prompt 240 px, demo 120 px). Every move is an integer number of modules and every landing is on a grid line.
- **Beat:** one action per beat at 120 BPM (0.5 s): a quarter circle turns 90° about a corner, a semicircle slides one module, a triangle flips, a square splits.
- **Pivots alternate** between own centre, corner and frame centre.
- **Easing:** power2.inOut or linear for moves, power2.in for drops (they land dead). No overshoot anywhere; the mechanical feel is the point.
- **Cascade:** a phase-shifted wave across the grid on the drop.
- **Ending:** Swiss typography (heavy geometric sans set vertically, small caps).
- **Print feel:** slight misregistration (demo plates: R (1.3, −0.9), B (−1.0, 1.2), K (0.5, 0.4) px), with paper tooth.

**Route:** SVG/Canvas on a module grid. The demo multiplies inks onto paper in a shader, and a 12-detent escapement (7.5° teeth, each moving in its last 65 %) ticks a group turn in time with the audio.

**Traps:**
- Overshoot.
- Off-grid landings.
- Gradients.
- Motion-blur sub-samples straddling a hard change (snap cut times to whole frames: `round(t·30)/30`).

**Sound:** minimal techno or clicks; a pitched click per flip, kick on quarters.

**Source:** mg-styles `prompts/09-bauhaus.md`, `demos/09-bauhaus/film.js`.

### Isometric 2.5D
**For:** miniature worlds: city/campus/server-room slices, architecture diagrams, app feature maps.

**Signature features:**
- **Projection:** true isometric with no vanishing point. Orthographic camera along (1,1,1): elevation 35.264°, azimuth 45°. 2:1 pixel slope along grid moves.
- **Look:** a pastel studio palette (lavender ground, mint, peach, sky blue, white) with soft shadows and AO.
- **Ground:** tiles drop in as a wave from the centre. Each falls 0.3 s, lands with a decaying squash, and gives two micro-bounces of 0.16 and 0.10 s.
- **Buildings grow:**
  - The base lands first.
  - Walls scale Y from 0 on a spring (ω 14.8, ζ .61: peak ~8 frames, ~9 % overshoot) with 6 % XZ squash.
  - The roof caps 2–3 frames later (a 0.1 s drop), then roof details 0.05 s after that.
- **Life loops:** cars, a train, drones, data pulses, a turbine.
- **Camera:** parallel slides only, no rotation; parallax layers at 1 : 0.8 : 0.6.
- **Ending:** a title set on the iso plane (text skewed into iso space).

**Route:**
- **Three.js:** `OrthographicCamera` + shadows + SSAO (demo: 16 samples, radius .55). The demo accumulates N sub-renders with Halton jitter for AA, soft shadows and motion blur.
- **SVG:** faces built by the SSR formula (scale Y 86.6 % → shear ±30° → rotate ∓30°), with z-order = screen y.

**Traps:**
- Any perspective.
- Camera rotation.
- Z-sorting errors when objects cross.
- Everything grows at once (stagger by distance from the centre).

**Sound:** bright plucky tech (FM marimba), soft clicks per landing, an airy whoosh on the pull-back.

**Source:** mg-styles `prompts/03-isometric.md`, `demos/03-isometric/js/world.js`, `render.js`, `anim.js`.

### Faceted low-poly poster (ambient loops)
**For:** calm art-first loops: website heroes, poster landscapes, waiting screens.

**Signature features:**
- **World:** flat vector with no outlines; every mass is cut into lit triangles.
- **Cells:** 50–75 px with low jitter (~0.22). Small cells read as noise.
- **Depth:** layers fade into haze, back to front: sky → far ridge (fade .55) → mid (.3) → mesas (.18) → floor and water → subject → dark foreground framing.
- **Columns:** split into a lit side and a shadow side.
- **Ramps:** plum → magenta → orange, or navy → blue → pale.
- **Subject:** the only outlined thing.
- **Loop:** every motion is periodic in the loop length; check frame 0 against the last frame.

**Route:** Canvas; bake each layer's facets once in `__ready`, move layers by `t`.

**Traps:** jittery small facets; motions not periodic in the loop length (a visible seam).

**Sound:** pads, sparse bells and wind in bars that divide the loop; a few diegetic sounds; no music hook.

**Source:** hanif `references/styles.md` § 5.

## 4. Editorial

### Sticker explainer (big canvas + camera)
**For:** dense knowledge and finance explainers, company "how it works" films. The serious, precise explainer look.

**Signature features:**
- **Stickers:** photos cut out with a thick white outline: 8–12 px in the prompt, 12–13 px in the demo, via SVG `stroke-width: 26; paint-order: stroke`. Each gets a soft shadow that grows with lift: `0 (6+34·lift) px (10+34·lift) px rgba(22,34,46,.26−.08·lift)`.
- **Palette:** calm blue-grey or off-white with 2–3 colours and one accent, e.g. `#E9EEF2` canvas, ink `#25313D`, mid `#8C9AA8`, accent `#FF5A36`. Equal-weight sans, strict alignment, a 48 px dot grid.
- **Canvas and camera:**
  - One huge canvas (the demo uses 2400×5900) with one continuous camera.
  - Long eases with log-lerped zoom: fly `cubic-bezier(.62,0,.22,1)`, pull `(.5,0,.08,1)`.
  - Moves of 0.26–0.65 s between information points, a 2.1 s pull-out at the end.
- **Beats:** every sentence of narration brings a new visual element.
- **Charts:**
  - Exact: bars to scale, consistent numbers.
  - Bars grow, count-ups follow easeOutCubic, leader lines draw on in ~0.28 s.
- **Sticker slap:** 0.2 s, scale 1.3 → 1, rotation 6° → 0, then a 4.5 Hz wobble (3.5 %, decay 10).

**Route:** DOM/SVG world under one camera transform (compose.html `camera()`). The demo adds velocity-driven directional blur on moving stickers.

**Traps:**
- Charts that aren't to scale.
- Mixed outline widths (this kills the unified sticker look).
- Hard cuts between points instead of the camera path.
- A beat with no new element.

**Sound:** a clean tech-explainer bed, UI clicks, ticking during count-ups, a soft whoosh on camera moves.

**Source:** mg-styles `prompts/19-paperclip.md`, `demos/19-paperclip/index.html`, `cues.json`.

### Collage / cut-out
**For:** surreal, editorial, music and streetwear; Monty Python meets constructivist posters.

**Signature features:**
- **Cut-outs:** photo cut-outs with a rough white scissor edge of 2–4 px. The demo dilates alpha with 28 offsets at r 3.5 px; the jaw rim is 11 px.
- **Texture:** halftone (7 px grid, dots up to 3.2 px) on newsprint or kraft.
- **Composition:** out-of-proportion surreal assemblies, with bold red/black diagonal type.
- **Puppets:** pieces rotate on shoulder, elbow and jaw pivots. The mouth uses 2–3 replacement drawings (closed / half / wide).
- **Stepped frame rate:**
  - Motion on 12 fps; resting pieces and the rostrum camera on 6 fps.
  - Placement jitter ±2 px / ±0.4° while moving, ±1.1 px at rest.
- **Slap-on:** 3 steps of scale 1 + 0.38u² before landing, then 0.972 → 1.01 → 1. The shadow collapses as it lands.
- **Transitions:** a hand slaps elements on, or the page flips/tears (the demo peels the page over a 100 px cylinder, showing the kraft verso).

**Route:** DOM/Canvas with PNG cut-outs; quantise time with `floor(t·12)/12`. Layers: paper → colour blocks → cut-outs → scribbles and tape → grain.

**Traps:**
- Smooth 30 fps motion (it reads as vector).
- Clean edges without the white rim.
- Assets you can't license (use CC0 / public domain).

**Sound:** vinyl crackle, a jazzy boom-bap bed, paper rustles, scissor snips, slaps, a comic pop.

**Source:** mg-styles `prompts/06-collage.md`, `demos/06-collage/index.html`.

### Kinetic captions (variety-show style, 9:16)
**For:** reactive captions over vlog, pet, interview or comedy footage; vertical social edits.

**Signature features:**
- **Layers:** multi-layer rounded heavy type, back to front:
  - 2 extrude copies;
  - an outer colour stroke (demo: 12 px, `#FF3D7F`);
  - a thick white stroke (13 px);
  - a gradient fill;
  - a gloss band (white .55 → 0 at 46 %);
  - a drop shadow (dy 12, σ 11, `#1a0a28` at .36).
- **Pop:** scale 0 → 1.15 → 1.0 in ~8 frames. The demo uses a spring with ζ .517, ω 22: peak at frame 5, ~1.01 at frame 8. Each character also drops ~90 px and rotates in from ±16°.
- **Stagger:** 1–2 frames per character.
- **Timing:** captions appear 2–3 frames after the audio or visual moment, never before.
- **Mood:** emotion-matched treatments: a radial burst frame with speed lines for shock, sweat drops for awkwardness, a skewed hand-written aside for asides, sparkles for delight.
- **Holds:** captions keep a wiggle, ramping in 0.2–0.6 s after the pop: rotation ~2°, bob 3–4 px at 1.15 Hz, a 1.2 % scale breath.
- **Exit:** 1.12 overshoot then collapse, ~5 frames.
- **Palette:** high saturation (pink `#FF3D7F`, yellow `#FFE14D`, cyan `#2CCBF2`) with white strokes and a navy outline `#1E2A78`.
- **Footage:** Ken Burns, light handheld shake, snap punch-ins (2-frame outExpo + 1-frame 3 % overshoot).

**Route:** DOM/SVG text, layered `paint-order` strokes or stacked copies, closed-form springs per character. Keep all captions inside the safe area (`layout.md`).

**Traps:**
- Captions that land before the joke.
- Thin strokes that vanish at phone size.
- Every caption with the same treatment.
- Fonts without the script's glyphs (tofu).

**Sound:** a bouncy variety bed (pizzicato, bass, claps); boing, pop, ding, slide whistle, record scratch.

**Source:** mg-styles `prompts/18-hanazi.md`, `demos/18-hanazi/index.html`.

*Kinetic typography (type as the whole film) has no dedicated card yet: our sources don't cover it as a
style. Use `craft.md` (masked word rises, stagger by register) and the morph and Bauhaus cards for type that
transforms or lands on a grid. hanif's "3D extruded type around live action" is one number-pinned move:
glyphs on a flat cylinder (vertical radius ≈ 11 % of horizontal), width = cos(angle), spinning ~0.34 rad/s,
landing on the headline facing camera for ~2 s, front half above a person matte and back half below.*

## 5. Light and FX

### Cyberpunk HUD / FUI
**For:** "a system is working": tech reviews, AI and security demos, aerospace, game edits. Film-UI density with restraint (Territory Studio).

**Signature features:**
- **Palette:** cyan linework on teal-black. The demo uses `#00E5FF`, dim `#0B7C8C`, deep `#0E3A42`, hot `#E8FEFF`, ink `#020A0D`. The alert state is orange-red (the prompt asks for `#FF6A00`; the demo re-inks toward ≈ `#FF6600` with a radial wave).
- **Build:** lines draw on (dashoffset) in staggered hierarchy: frame → rings → data.
- **Elements:** concentric rings with ticks, a conic radar sweep with blips, a 30 px hex grid, sparklines, a wireframe hologram.
- **Numbers:** they roll randomly for 3–5 frames, then settle on the real value. The typewriter runs ~110–120 chars/s for status lines and ~34 for coordinates, with a blinking cursor.
- **Lock brackets:**
  - Four corners fly in over 8 frames (outCubic), then snap through per-frame keys 1.35 → 1.08 → 0.96 → 1.0 (the prompt says 1.4 → 1.0).
  - Three trailing echoes, 2 frames apart, at alpha .12 / .25 / .45.
- **Finish:**
  - Glow, then slight radial chromatic aberration.
  - Scanlines: 3 px period at ±10 %.
  - Restrained micro-glitches.

**Route:** SVG/Canvas layers, Three.js wireframe, one post pass. Composite type glow after bloom so glyphs stay crisp.

**Traps:**
- Lorem-ipsum density with no hierarchy.
- Everything glowing.
- Unseeded random numbers (they change on re-render).
- Text that blooms into mush.

**Sound:** darksynth pulse, HUD beeps, scan sweeps, an ascending lock-on tone, an alarm on lock.

**Source:** mg-styles `prompts/22-hud.md`, `demos/22-hud/js/hud.js`, `post.js`.

### 80s synthwave / VHS
**For:** retro title sequences, music, nostalgia campaigns (also the base for Y2K chrome).

**Signature features:**
- **Scene:** a starry sky over a deep purple gradient; a striped retro sun (~11 band cut-outs on the lower ~69 %, gaps widening downward, scrolling); wireframe mountains, palms; a magenta/cyan perspective grid rushing at the camera.
- **Grid motion:** in the demo it surges 18 → 61 units/s toward the title slam.
- **Double glow:** tight ~4 px + wide ~30 px. The demo's neon script uses shadowBlur 34 then 5; the grid is analytic, `exp(−d/3.4) + .16·exp(−d/15)`.
- **Chrome title:** a multi-stop metallic gradient, bevel highlight, a star glint and lens flare on the slam. Neon script writes on like a tube, with flicker.
- **VHS chain:**
  - RGB split 1–2 px (demo 1.2 px, 2.2 px on glitch), then scanlines.
  - The prompt asks for 2 px / 10 % black; the demo darkens every 3rd line by 12 %.
  - Wave distortion and 2-frame glitches 1–2 per second, with row tears 6–20 px high shifted 8–40 px.
  - A 4:3 rounded mask (38 px corners) that opens to full frame.
- **Unstable frame rate:** some spans drop to 15 fps, and 2 frames play backwards at a "rewind".

**Route:** WebGL (grid, sun, mountains) + Canvas chrome text + a post pass. Use energy-conserving smear on grid lines so they don't strobe at speed.

**Traps:**
- Glow on everything (keep the hierarchy).
- A grid that strobes.
- A VHS pass so heavy the title is unreadable.

**Sound:** synthwave: gated-reverb snare, arpeggiated saw bass, lush pads, a big chord and crash on the title slam.

**Source:** mg-styles `prompts/10-synthwave.md`, `demos/10-synthwave/index.html`.

### Aurora + glassmorphism
**For:** the 2024–26 AI/tech product look: slow, translucent, expensive.

**Signature features:**
- **Aurora:**
  - Large blurred colour blobs drifting on closed bezier loops of 20–40 s, blending into a mesh gradient. The prompt says 3–5 blobs at blur 80–150 px; the demo uses 7 analytic Gaussian blobs of r 240–560 px, domain-warped by noise.
  - Adjacent hues only (violet / blue / cyan / magenta). Complementary colours go muddy.
  - A dark base works better than a light one.
- **Glass cards:**
  - Backdrop blur 20–40 px (demo: 30), 5–10 % white fill, a 1 px inner highlight at ~30 % white (the demo varies it 14–70 % by facing the light), radius ~40 px.
  - They float in with parallax depth and a slight 3D tilt (20°·e^(−3.2τ)·cos(3.6τ)).
- **Micro-UI and text:** enters by opacity + 8 px rise only (easeOutCubic 0.7–0.95 s, words 0.06 s apart).
- **Optional "Liquid Glass" lens:** true refraction, IOR 1.5, chromatic dispersion on the rim, magnification 1 → 1.36 → 1.2.
- **Grain:** 3–5 % noise and a ±1/255 dither against banding.
- **Easing:** sine/breathing curves everywhere; nothing fast.

**Route:** a WebGL shader for the aurora, DOM `backdrop-filter` cards (or shader glass), light sans type. Where light pools overlap, let them get hotter rather than muddier (`smoothstep(.75, 2.1, weightSum)`).

**Traps:**
- Any fast move breaks the mood at once.
- Banding on dark gradients (render with `--grain`).
- Complementary colours.
- Glass with nothing behind it to refract.

**Sound:** an ambient cinematic pad, soft shimmer, very subtle UI ticks.

**Source:** mg-styles `prompts/12-aurora-glass.md`, `demos/12-aurora-glass/main.js`, `shaders.js`.

### Liquid
**For:** music, food and drink, organic transitions, logo genesis.

**Signature features:**
- **Look:** glossy, thick liquid: specular highlights, a fresnel rim (Schlick, F0 .04), an 8–12 px meniscus band inside the edge.
- **Metaball fusion:**
  - Stretched necks that snap, with a 2–3 frame rebound at each end.
  - Cheap route: blur 20 px+ → alpha threshold (`feColorMatrix`). The demo uses a true SDF smooth-min.
- **Secondary droplets:** they follow 2–3 frames late and squash flat on landing.
- **Flood transition:** a wavy front with 3–5 phase-offset bulges. The demo stacks sines at ×1, ×1.87, ×3.13 plus a Gaussian mound, in three sheets staggered 0.07 s.
- **Ease:** flung, never uniform: `cubic-bezier(.22,1,.36,1)`. Springs for the landing squash (6 Hz), the pinch recoil (7 Hz, ζ .45) and the thread snap (5.5 Hz, ζ .32).
- **Logo:** text SDF blended with the blobs.
- **Palette** (demo): a candy gradient (hot orange → pink → violet) on deep plum.

**Route:** a WebGL2 fragment shader with 2D SDF metaballs and fake 3D lighting from the field gradient. Blur edges by their per-frame speed in the shader so the rim streaks instead of strobing.

**Traps:**
- Flat blobs with no light (they read as 2D goo).
- Uniform speeds.
- Perfectly straight edges anywhere.

**Sound:** bubbly gloops, pour, splash, drip, a deep bass swell under a glossy synth bed.

**Source:** mg-styles `prompts/07-liquid.md`, `demos/07-liquid/js/scene.js`, `shaders.js`.

## 6. Retro and 3D

### Pixel art
**For:** game and indie launches, 8-bit nostalgia, playful brands.

**Signature features:**
- **Resolution:** low internal resolution scaled up by an integer with nearest-neighbour (demo: 320×180 ×6 → 1920×1080, push-ins step ×6 → 8/10/12).
- **Palette:** limited to 8–32 colours (the demo has a 32-colour indexed palette with per-scene LUTs and colour cycling at 10 fps). Gradients use 4×4 Bayer dithering.
- **Sprites:**
  - Authored as pixel arrays at 16×16 to 24×24.
  - Run cycle 6–8 frames at ~10–12 fps (demo: 6 frames, a new one every 3 output frames); breathing 2–4 frames; coins 4 frames.
- **Positions and timing:** whole pixels only, and stepped timing (`steps()`), never smooth easing on sprites.
- **Parallax:** 3–4 layers moving by whole pixels (demo: ×0.06 / .125 / .3 / .55).
- **Type:** dialogue boxes type at 1 char per 3 frames; a shine band sweeps across the logo.
- **Optional CRT pass:** scanlines, slight barrel (k .03), phosphor glow. It must not smear pixels: sample sharp-bilinear.

**Route:** Canvas at internal resolution, `imageSmoothingEnabled = false`, scaled with CSS `image-rendering: pixelated` or a final integer `drawImage`.

**Traps:**
- Sub-pixel positions (shimmer).
- Anti-aliased edges.
- Smooth easing.
- A non-integer scale.
- A CRT pass that blurs everything.
- Motion blur on sprites: keep them out of `__meta.blur` (inferred).

**Sound:** chiptune (pulse lead, triangle bass, noise drums) plus jump, coin and chest SFX.

**Source:** mg-styles `prompts/20-pixel.md`, `demos/20-pixel/film.js`.

### 3D render (Blender route)
**For:** premium product films, brand idents, soft "satisfying" ASMR looks (C4D / Octane pastel).

**Signature features:**
- **Materials and light:** PBR (SSS gummy, glossy plastic with clearcoat, frosted glass or chrome), shot in a pastel studio: infinite cyc, big soft area lights + HDRI, AO.
- **MoGraph field:** a cloner field (grid of pills or spheres) rippled by an effector wave. A hero object drops in with a damped squash-and-stretch jiggle and displaces the field.
- **Camera:** long-tail ease (80 % of the travel in the first 20 %); ends on a held hero composition (~1 s).
- **Lens and motion:** shallow depth of field (f/1.8 feel), 24 fps, real motion blur at a 180° shutter.

**Route:**
- **Blender CLI** (`bpy` script): Cycles GPU (demo: 24 adaptive samples, threshold .035), OIDN denoise, PBR Neutral view transform.
- **Gummy:** Burley SSS, radius (1, .5, .8), scale .11, coat .45. **Chrome:** roughness .045.
- **Output:** a PNG sequence, then type and grain in an HTML overlay pass, rendered with this skill's renderer over the frames.
- **Hero punch on impact:** scale 1.035 → 1 over 6 frames plus a 4-frame shake.
- (The demo's camera ease, DOF and springs live in a baked keyframe file that isn't in the repo, so those numbers aren't verified.)

**Traps:**
- Chrome reflecting black (lift the HDRI's darks for reflections only).
- Noisy renders at low samples (denoise).
- A linear camera.
- Plasticky, flat lighting.
- Real brand trademarks.

**Sound:** ASMR soft thuds, squishes, bubbly pops, an airy cinematic pad; hits frame-synced to impacts.

**Source:** mg-styles `prompts/04-3d-render.md`, `demos/04-3d-render/blender/scene.py`, `index.html`.

## 7. Checking a film against its card

For the critic (or yourself before delivery):

1. **List every signature feature of the card** and find a timecode where each is visible. Example: "boil: 1.20–1.40 s, 3 drawings cycling; off-register fill: 2.3 s, (−5, +4); smear: 0.38 s, one frame". A feature with no timecode is missing.
2. **Measure, don't eyeball.** Step through the fast spans frame by frame (`qa/sheets.sh` strips):
   - Is exposure on 2s where the card says so?
   - Does the pop really overshoot 1.15 over ~8 frames?
   - Do sprites move by whole pixels?
   - Does a Bauhaus move land on a grid line?
3. **Check the anti-features**, the things the style forbids:
   - overshoot in Bauhaus;
   - a fast move in aurora glass;
   - smooth easing on pixel sprites;
   - gradients in flat vector;
   - motion blur on held cel drawings;
   - perspective in isometric.
4. **Check the numbers the series locked** (palette hex, line weight, exposure, boil amplitude) against the previous film in the series. Report drift with the number.
5. Report as fixes with timecode and number ("2.4 s: lock brackets land at 1.0 with no 1.35 snap"), ordered by how much each would change what a viewer sees. Not a score.

## 8. Sources and licences

- **mg-styles-15** by Vincentwei1021: https://github.com/Vincentwei1021/mg-styles-15 (MIT). Code, prompts and films are MIT; third-party assets (VCSL samples, HDRI, photos, Natural Earth) are CC0 or public domain; glyph outlines are OFL. Each card's prompt and demo path is relative to this repo, e.g. `https://github.com/Vincentwei1021/mg-styles-15/blob/HEAD/prompts/05-cel-boil.md`. The prompts' signature-feature sections are in Chinese; the numbers here are translated and checked against the demo code.
- **claude-animation-skill** by buildwithhanif: https://github.com/buildwithhanif/claude-animation-skill (MIT). `references/motion.md` (exposure, boil, snap-then-hold), `styles.md` (editorial, brush-watercolour, low-poly, 3D type ring), `traps.md`.
- `templates/drawn.js` reimplements ideas from both. It doesn't copy the code; it credits them in its header.
