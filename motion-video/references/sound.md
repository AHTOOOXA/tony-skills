# Sound and music

You can't hear, so the toolkit makes sound measurable: `beats.py` reads a track's structure, `mix.py` builds
the mix from a spec, `qa/verify_audio.py` checks it. When the choice is taste (which track, music or not),
render 2–3 variants — that's cheap — and let a human pick by ear.

## Contents
1. Cutting to music (+ a generated bed: `music.py`)
2. Principles
3. The mixer's model
4. Recipes per event (+ velocity-driven foley)
5. Sources and licences (+ finding assets, measured tracks)
6. Lessons

## 1. Cutting to music

Most films that landed were cut to music: state changes on beats, big moments on downbeats, the hero on the
drop. Workflow:
1. Pick a track that fits the idea's energy (60–80 BPM cinematic/regal, 90–110 smooth/cool, 115–123
   kinetic, faster = hype). Sources: `mixkit-music:<id>` (free, commercial OK; find IDs with
   `find_sound.py music <genre|mood/x>`, §5), Pixabay music, a licensed library the user has; generative
   (ElevenLabs Music, Stable Audio) on paid/commercial terms; or a bed generated to the cues (below).
2. `uv run --with librosa python scripts/beats.py <track> --len 15 --drop-at 4` → tempo, beats, downbeats,
   sections, the drop (found by low-band energy, not an auto grid), and the cut window that puts the drop
   where you want it in the film.
3. Build the timeline on `window.beats_in_film` / `downbeats_in_film`; moves that land on a beat start
   40–190 ms early; reveals can shift ≤ 0.15 s toward a strong beat; readability wins over sync.
4. In `sound.json`: `"bed": {"asset": "track", "kind": "music", "offset": <window.start>, "lufs": -20}`,
   SFX on top with modest lifts (music carries energy; SFX accent touches). Without music, a room/ambience
   bed and tactile SFX can carry an intimate film — a deliberate choice, not a default.

**A generated bed (`scripts/music.py`) — an option, not the default.** It wraps mgaudio (the `lib/audio`
of mg-styles-15, MIT; samples VCSL, CC0): a recipe arranges intro → build → drop → outro on a grid whose bar 0
sits on `--drop`, the final chord starts at `--outro`, length = `--len`; with `--hits` (≥ 2 cue times) and no
`--bpm` it fits the tempo so the hits sit on its 8th-note grid. Recipes: synthwave, darksynth, vaporwave,
chiptune, techno, acid, pop, future_bass, trap, glitch_hop, lofi, ambient (flavors glass/product/piano),
guofeng, variety, explainer (`music.py list` shows keys, progressions, extras and which look each was made
for). Writes a WAV for `"bed": {"kind": "music", "offset": 0}` and `<out>.json` with BPM, sections and
beats/downbeats in film time for the comp. Licence-free, deterministic, ~10 s to render. Be honest about it:
- **Nobody has validated how it sounds** — we can't listen, and its author's demos are 10 s clips. Render it
  next to a stock track (same cues, two `sound.json` variants) and let a human choose by ear.
- The repo is incomplete: its README points at `examples/*.py` and `SAMPLES.md` that aren't there, and
  `samples/index.json` lists 598 VCSL files in 42 instruments, of which 102 files in 15 ship (piano 39/73; no
  shaker, triangle, gong or guzheng). `music.py` re-indexes to what's on disk, so missing instruments fall back
  to mgaudio's synth versions — the sound differs from the author's renders; in an earlier check only 4 of its
  15 demo soundtracks reproduced bit-exact.
- `fit_bpm` finds the best compromise, not a perfect grid: 5 hits at 1.5/2.6/3.9/5.4/7.2 s → 84.5 BPM with a
  79 ms worst error. Move the picture to the grid (`beats` in the sidecar) where it matters, not the sound.

Sound that tends to read cheap: a raw sine or noise burst per event, a melody that fights the picture,
everything at the same loudness, never a quiet moment. Synthesized sound can be great (Voxyz synthesized
the music for "small print") — what matters is that it's designed.

## 2. Principles (cross-source, all defaults)

- Every sound is caused by something on screen; **fewer sounds than events** (in a staggered group accent the
  first, last or strongest; montage stickers stay silent). Two anchors within 40 ms → keep one.
- **Place by the measured peak** (hits) or **onset** (strokes, swells): `align: "peak" | "onset"`.
- Entry sounds can lead the first visible frame by 0–0.1 s; a "success" lands when the element is settled.
- **One room**: a shared reverb send for every SFX (send 0.1–0.6 by distance), pan by screen x (±0.6).
- **Layers**: transient (the recording, low-passed ~9 kHz) + body (a soft impact 8–12 dB under) + tail (the room).
- **Pitch**: tonal sounds in one key; a sequence of similar hits steps up (+0/+1/+2 semitones left → right).
- **Silence is a tool**: drop the bed for 0.3–0.5 s before the hero hit (`silences`); rests are quiet.
- **The hero** (brand reveal / payoff) is the loudest momentary moment by ≥ 2 LU. A **sonic logo** (a short
  distinctive sound — a purr, a "mrr") links to the brand far better than a slogan (TikTok study: > 8×).
- **Calm first 3 s**: no phone rings, notification pings, alarms or hits (they raise skip rate). A soft tick is fine.
- **Phone speakers** play little below ~300 Hz: a sub-only sound vanishes. Keep a mid/high layer on every
  important event; `verify_audio.py` checks each event through a 300 Hz–8 kHz band.
- Music, if any: 90–110 BPM for calm/anxious audiences (60–80 cinematic, 115–123 kinetic); find the drop by
  low-band energy, not an auto beat grid; start the track so its lift lands on the key visual; moves that land
  on a beat start 40–190 ms early. Music ~11 dB under a voice-over, ducking 150 ms down / 400 ms up.
- Master: −14 LUFS integrated, true peak ≤ −1.5 dBTP after AAC (aim −2.0 in PCM).

## 3. The mixer's model

- `lift` = how far the event's **loudness** sits over the bed where it lands, K-weighted (as the ear hears):
  a hit's 50 ms around its peak if it's a spike (peak > its loudest 400 ms + 12 dB), otherwise its loudest
  400 ms. Never "the 400 ms after the onset" — a harp sweep starts near-silent and got boosted +16 dB.
- The bed holds its **absolute** level (`bed.lufs`, e.g. −27 rain, −31 very faint). A continuous bed dominates
  integrated loudness, so normalising the whole mix to −14 would drag it up to ~−18. The master's gain lands
  on the events: `lift` is the balance between events; the report prints Δ (every event = lift + Δ over the bed).
- Lifts for long sounds (whooshes, sweeps, sparkles) stay low (0–3): their loudness is their whole body.
  Hits 7–10, the hero 12–14.
- The master protects transients: the limiter may take ≤ 8 dB off the loudest peak. A sparse SFX mix then
  lands 2–6 LU under −14 — accepted (denser sound or a louder bed to go louder). Don't use pedalboard's
  `Limiter` for final level (it adds make-up gain) or ffmpeg `loudnorm` on sparse mixes (it falls back to
  dynamic mode and lifts the quiet parts — the bed came out 10 dB too loud).

## 4. Recipes per event

| Event | Layers (relative to the event's loudest layer) |
|---|---|
| card flip / card place | `kenney:casino/Audio/card-slide-N` or `card-place-N` LP 9 kHz, 0 dB · `kenney:impact/Audio/impactSoft_medium_00N` LP 2.5 kHz, −10 dB · room 0.2–0.25 · pitch +0/+1/+2 across a sequence |
| tap | `kenney:ui/Audio/click3.ogg` HP 300 / LP 8 kHz, lift 7, dry-ish |
| label / sticker landing | card-place LP 9 kHz + soft body −8 dB (+ 120 ms of a paper slide 30 ms earlier, −14 dB) |
| iris open | a soft air whoosh (`mixkit-sfx:1489`) peak at the iris start, lift 0; or a reverse swell ending at the iris; the ambience low-pass opens 3.5 → 9 kHz across it ("the window opens") |
| iris close | mirror; then the 0.3–0.5 s silence before the hero |
| marker / pen stroke | `mixkit-sfx:2367` trimmed to the stroke, onset-aligned, lift 6, high shelf −3 dB above 6 kHz |
| screen slide | `mixkit-sfx:1530` paper slide, peak at the swap, lift 7; accent first/last only in a long series |
| magic reveal | `mixkit-sfx:2353` glitter / `871` sparkle, lift 2–4, room 0.5–0.6 |
| clock tick | `mixkit-sfx:1060` (ticks at 1.34 s, 2.34 s…), trim 0.3 s, 2–3 ticks max, then stop on the story beat |
| hero / brand | 0.3–0.5 s near-silence, then a sonic logo (purr `mixkit-sfx:3091`) + a bell `3109` −3 dB for phone speakers (+ optional warm `impactSoft_heavy` body); lift 13–14 |
| ambience bed | rain `mixkit-sfx:2474` (LP 5 kHz, "through a window"), crickets `1787` (LP 3.5 kHz); −27…−31 LUFS |
| tactile tap / tick | `vcsl:woodblock/ff` or `vcsl:claves` HP 200, lift 7; alternate `rr1`/`rr2` takes in a series (no machine-gun repeats) |
| comic slap / snap | `vcsl:slapstick` (5 takes: `find_sound.py vcsl slapstick`), lift 8, dry |
| musical sting / sonic logo | real mallets, in the bed's key: `vcsl:glock/medium C6`, `vcsl:kalimba/C#4`, `vcsl:marimba/C4 med`, `vcsl:vibraphone/A4 v2` (trim 1–1.5 s) + a soft `vcsl:triangle/hit v2` −6 dB on top for phones; lift 12–14 for the hero |
| shaker / rustle texture | `vcsl:shaker/Down` + `/Up` alternating on a beat, lift 2–4, `"texture": true` |

**Velocity-driven foley** (mg-styles' line-art demo): the sound of a moving thing is as loud as the thing is
fast. A pen/marker scratch follows the tip's speed (quiet into a corner, loud on the long stroke, silent when
it lifts); a whoosh's length ≈ the travel time and its peak = when the object crosses the centre of frame;
its loudness swells with the speed curve and the pan follows x. `mix.py` does this per event:
`"speed": [[t, v], …]` (film time; t may be `"cue:…"`) or a JSON file (`{"t": […], "v": […]}` or
`{"fps": 60, "speed": […]}` dumped from the comp's path) → gain = (v / v_max)^0.6 (`speed_exp`), smoothed at
30 Hz; `"loop": true` repeats a short texture (only its sounding part, 50 ms crossfades) to the curve's end.
```json
{"sound": "pen", "t": 8.0, "align": "onset", "lift": 4, "speed": "pen_speed.json", "loop": true, "texture": true}
{"sound": "air", "t": "cue:hero-0.15", "lift": 1, "speed": [["cue:hero-0.9", 0], ["cue:hero-0.15", 1], ["cue:hero+0.2", 0.2]]}
```
Measured: a speed dip 1300 → 150 px/s mid-stroke dropped the pen 13 dB there and back. Without a curve, apply
the rule by hand: trim the whoosh to the move's duration and put its peak (`align: "peak"`) on the centre crossing.

Generative alternative (paid ElevenLabs SFX, `POST /v1/sound-generation`, 0.5–30 s, `prompt_influence`
0.5–0.7; or Stable Audio 3 Small SFX locally): "close-mic single paper tarot card flipped and slapped flat onto
a wooden table, dry room, one-shot" · "chisel-tip highlighter dragged across paper in one slow stroke, close mic"
· "black cat short soft purr then a quiet 'mrr' chirp, close-mic, intimate, dry".
Voice-over A/B: a human-like whisper of the hook (TTS, words timed with whisper.cpp). TikTok's ad study:
voice-over + offer +87 % conversion.

## 5. Sources and licences

| Source | Commercial ad | Attribution | Notes |
|---|---|---|---|
| Kenney (CC0) | yes | no | best free foley for cards/UI/impacts; `kenney:<pack>/<file>` in `mix.py` |
| VCSL (CC0) | yes | no | real recorded piano, kalimba, glockenspiel, marimba, vibraphone, chimes, woodblock, claves, slapstick, triangle, shaker, tambourine, timpani … `vcsl:<alias>[/<words>][@n]` in `mix.py`, downloaded per file on first use, licence written next to the cached file; aliases and files: `find_sound.py vcsl [alias]`. Note names come from file names (mg-styles measured the kalimba ~an octave above its labels) |
| mgaudio / `music.py` | yes (MIT code, CC0 samples) | no | generated beds, see §1; listen before you ship |
| Mixkit SFX / music | yes | no | don't redistribute the files (cache, don't commit) |
| Pixabay sounds | yes | no | no standalone resale |
| Freesound CC0 only | yes | no | CC-BY needs credit; NC is not usable |
| Sonniss GDC bundles | yes | no | no redistribution; no AI training |
| ElevenLabs SFX / Music | paid plans only | free plan: credit + non-commercial | generate finals while subscribed |
| Stable Audio 3 (open weights) | yes under $1M revenue | no | runs locally |
| BBC RemArc, Udio, Freesound NC | no | — | |

**Finding assets.** `scripts/find_sound.py` (stdlib; cached 7 days, ≤ 1 request per 1.5 s):
`sfx <tag…> [--grep word]` → `mixkit-sfx:<id>` with length and tags (`sfx` alone lists the 276 tags: `write`,
`paper`, `whoosh`, `click`, `bell` …); `music <genre|mood/x|instrument/x|tag/x> [--pages 3] [--grep piano]
[--max-len 150]` → `mixkit-music:<id>` (Mixkit's search ignores `?q=`, so it crawls those pages; `music` alone
lists them); `vcsl [alias] [words]` → CC0 files (needs `uv run --with librosa`). Then measure, don't trust titles.

Mixkit SFX others have used (claude-motion-design, not re-checked by ear): click 1125, key 2568, soft tick
1117, check 1113, toggle 1120, toast 2573, pop 2364, bubble 2357, soap 2925, whoosh 1490, rise 1489, impact 1143,
shutter 1430, lens 1433, sparkle 3083, success 2865; pen on paper 2367, pencil 2376/3194, marker line 2998.

Measured Mixkit tracks — source: claude-motion-design (CMD, hand-checked drops) vs `beats.py` here (2026-10-09):

| ref | track | CMD | beats.py |
|---|---|---|---|
| `mixkit-music:129` | — | 120 BPM, drop 16.09 s | 117 BPM, drop 16.10 s |
| `mixkit-music:190` | — | 120 BPM, drop 16.01 s (bar 8) | 117 BPM, strongest jump 63.5 s; 15.07/17.21 in sections |
| `mixkit-music:207` | — | 120 BPM, drop 31.97 s | 117 BPM, strongest jump 89.0 s |
| `mixkit-music:364` | Waka Floka Type (Arulo), trap | drop 14.75 s | 129 BPM, drop 14.75 s |
| `mixkit-music:371` | Cat Walk (Arulo) | 130 BPM, drop 14.769 s | 129 BPM, drop 15.45 s (13.65 in sections) |
| `mixkit-music:357` | Head Bang (Arulo), half-time hip-hop | 74 BPM, 4-bar quiet intro, drop 12.96 s | 74 BPM, strongest jump 51.9 s |
| `mixkit-music:32` | Driving Ambition, uplifting piano | ~99 BPM, hit 37.66 s | 99 BPM, drop 38.55 s |
| `mixkit-music:684` | Classical vibes 4, Apple-ish classical | ~94 BPM, lift ~7.95 s | 92 BPM, drop 8.57 s |

Read it as: `beats.py`'s `drop` is the single biggest low-end jump in the whole track, which for a 15 s film is
often not the drop you want — an earlier one sits in `sections`. And its tempo read 117 on three tracks CMD
measured at 120: check the grid against a downbeat or two before you hang 30 cuts on it.

## 6. Lessons

- Fixed gains made every event inaudible (measured lift −4…+2 dB). Adaptive lift over the bed fixed it.
- Measuring a low-frequency purr in raw RMS made the hero 9 LU too quiet; K-weighting fixed it.
- A loud bed + normalising to −14 = a mix that is mostly rain. Hold the bed absolute.
- A swell measured after its onset got +16 dB and its tail became the loudest moment of the film.
- `verify_audio.py` named each of these within one run — run it after every change. `--png spec.png` draws
  the spectrogram + loudness curve with events (hero in gold), cues and silences marked: Read it — a sound
  that landed off its cue, a bed that didn't drop out, a hit with no mid/high layer show at a glance. Its band
  warnings (sub > 45 %, 2–5 kHz > 7.5 %, nothing above 5 kHz, < 18 % under 250 Hz, a gap > 0.6 s) come from
  mgaudio's qc, calibrated on music masters: hints, not fails — a bell-led SFX mix reads "harsh" by that table.
