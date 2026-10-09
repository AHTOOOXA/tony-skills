# Voice as the clock

When the words carry the claim (an explainer, a product demo, a tutorial, a narrated story), the voice drives
the cut instead of music. Every beat lands on the word that names it, captions come from the same timings,
and music becomes a bed that ducks under the voice. Any voice works: a TTS export from any vendor, a local
model, `say` for a draft, or a human at a microphone. The tools only need an audio file and the script.

## Contents
1. Workflow
2. Keying the picture to words
3. Pacing
4. Captions
5. Music and SFX under a voice
6. The STT check
7. Numbers and lessons

## 1. Workflow

1. **Write the script first** and read it aloud. Put a blank line between sections (a section is one idea,
   usually one scene). `#` lines are notes and aren't spoken.
2. **Record or TTS one file per section.** That way you can redo one section without touching the others.
   Before you commit to a voice, audition the same two lines in a few voices and let a human choose by ear
   (onetake). Clients change their minds, so the timeline has to survive a voice swap.
3. **Tidy and time it:**
   ```bash
   uv run --with numpy --with soundfile python scripts/vo.py all s1.wav s2.wav s3.wav --script script.txt -o vo.wav
   ```
   → `vo.wav` (silence trimmed, pauses squeezed, 0.5 s lead), `cues.json` (`s1`, `s2`, …, `vo_end`),
   `words.json` (`[{w, t0, t1}]`, spelled as in the script), `captions.json`.
4. **Build the comp against `words.json`/`cues.json`** (§2), never against typed-in seconds.
5. **Mix:** add a `voice` block to `sound.json`, put the music or ambience bed under it, hang SFX on
   `"word:…"`/`"cue:…"` (§5).
6. **Run `vo.py check` on the final MP4** before delivery (§6).

If you re-record or swap the voice, re-run step 3 and re-render. The comp and the mix re-time themselves
because every time is read from the files.

## 2. Keying the picture to words

`templates/compose.html` has `loadJSON(path)`, which works under `file://` with `render.mjs`, and
`word(words, text, nth = 1)`, which returns the `t0` of the nth occurrence of a single word. It ignores case
and punctuation and throws if the word is missing.

```js
let WORDS, CUES;
window.__ready = (async () => {
  WORDS = await loadJSON('words.json');
  CUES  = await loadJSON('cues.json');
  T.pick  = word(WORDS, 'select');      // the cursor clicks as the voice says "select"
  T.logo  = word(WORDS, 'lumora', 2);   // the second "Lumora" is the brand reveal
  T.scene2 = CUES.s2;                    // section 2 starts here
  window.__meta = { duration: CUES.vo_end + 1.2, fps: 30, width: W, height: H, cuts: [T.scene2] };
  // fonts, images, setWords …
})();
```

- Key a beat to the **start of the word that names the thing** (claude-animation). If a move should land on
  the word, start it 40–190 ms early, the same lead you'd give a move that lands on a musical beat.
- Name the word next to each beat in the beat sheet (`T.pick  // "select"`). A new voice then means
  re-reading `words.json`, not re-deciding the film (onetake).
- `render.mjs` reads `__meta` after `__ready`, so the duration can follow the voice.

## 3. Pacing

- **The film's length follows the voice.** Never space lines out to fill a length. Measure first, then
  promise a length: TTS pauses at punctuation don't shrink when you raise the speed (onetake).
- **Continuous narration:** inner pauses about 0.28 s, about 0.45 s breaths between sentences and sections.
  Hold a longer gap (`--pause 4:2.0`) only where the picture carries on alone, such as a scroll or a reveal
  with music. A slight speed-up (`--tempo 1.05`) often helps a slow TTS voice (claude-motion-design).
- **A new picture every 2–4 s** (claude-motion-design). In narrated explainers that works out to roughly one
  scene per sentence, about 3.5 s each. Narration runs at about 150 words/min (2.5 words/s), so a scene
  holds about 8–10 words. If a sentence runs longer than about 5 s, give it two pictures.
- **Build the hook first.** Spend the first 3 s on the hook, picture and line together, and get it right on
  its own. Then build the blocks in order, one section at a time, and look at each through a contact sheet
  (`render.mjs --stills` at its word times) before starting the next. A narrated film is long enough that a
  mistake in block 2 is expensive to find at the end.
- Picture and voice should tell the same thing at the same moment. Don't show feature B while the voice is
  still on feature A, and don't show a number before the voice says it.

## 4. Captions

`captions.json` gives `[{text, t0, t1, words: [i0, i1]}]`. Chunks are at most 42 characters (`--max`). They
break at punctuation and pauses and never cross a sentence. There are no flicker gaps under 0.3 s, and every
chunk stays at least 0.7 s. `vo.py` warns about chunks over 17 chars/s. Lay them out per `layout.md`: inside
the safe area, at most 2 lines, a readable size at phone scale. For karaoke, use `words: [i0, i1]` to light
each word on its own `t0`, never before (claude-motion-design). Caption text keeps the script's spelling, so
brand names come out right even when the ASR heard them wrong.

## 5. Music and SFX under a voice

```json
"voice":  {"src": "vo.wav", "lufs": -16, "offset": 0, "duck": {"depth": -11, "attack": 0.06, "release": 0.35}},
"bed":    {"asset": "music", "kind": "music", "lufs": -20, "offset": 12.0},
"events": [{"sound": "tap", "t": "word:select", "lift": 7},
           {"sound": "bell", "t": "cue:logo", "align": "onset", "lift": 13, "duck": false}]
```

- **The voice sets the loudness.** It lands at `voice.lufs`. The bed holds `bed.lufs` and ducks `depth` dB
  under the voice envelope: it is already down when the first syllable lands, it holds through the gaps
  between words, and it comes back up over 350 ms. SFX are not ducked. The master glues and limits the mix
  but doesn't push it toward `master.lufs`. The report prints how far the bed sits under the voice. About
  11 dB under the speech reads clearly (onetake). Raise `bed.lufs` if the music disappears in the gaps.
- **Times can be references.** Any time in `sound.json` can be `"cue:name"`, `"cue:name+0.05"`,
  `"word:select"` or `"word:pick a card#2"` (a phrase, second match). Cues come from `cues.json`, words from
  `words.json`, and word times include the voice offset. A name that doesn't exist stops the mix. Add your own
  cues to `cues.json`, e.g. `"logo": "word:lumora#2"`. `vo.py tidy` merges its section starts into the same
  file without touching your cues.
- An SFX that lands on a stressed syllable gets masked by the voice. Place it just before the word, or in a
  breath.
- `qa/verify_audio.py`'s "quiet" leg fails on a narrated film because a voice-over is never quiet. That
  failure is structural, so don't tune the mix to pass it (onetake). The other legs still apply.

## 6. The STT check

```bash
uv run --with numpy --with soundfile python scripts/vo.py check final.mp4 script.txt
```

This runs ASR on the delivered mix (music, SFX and all) and diffs it against the script. It reports the word
error rate and lists every mismatch with its time, and exits 1 over `--max-wer` (2 %). It catches a TTS voice
mispronouncing the brand, a word clipped by an edit or by `tidy`, music masking a line, and a section left in
an old take. Number spellings ("20" vs "twenty") are listed for you to check by ear but not counted. Anything
heard before the first word or after the last (lyrics, music) isn't counted either. If you can, have a human
listen once too.

## 7. Numbers and lessons

- **Word timing accuracy**, measured on a file with known word onsets: whisper.cpp large-v3-turbo with DTW
  plus `vo.py`'s calibration put word starts within 62 ms on average (155 ms worst); faster-whisper `base`
  was within 110 ms. That's ±2–4 frames. For a hit that must be frame-exact, nudge it by eye from a frame
  strip.
- Raw whisper.cpp DTW times run about 0.25 s late and faster-whisper runs early, so `vo.py` calibrates on the
  audio. Words that open a sentence or clause must start where the voice starts after a pause, and their
  median miss is subtracted from every word. Pairing every word with its nearest onset slipped by one word on
  a 0.4 s rhythm.
- ASR spells invented names its own way (often the nearest real word), writes numbers as digits and invents
  words over silence. That's why alignment keeps the script's words and only uses the ASR's times.
- The defaults come from TTS behaviour: engines stop about 0.6 s at every full stop, and 0.28 s inner pauses
  read as one speaker talking (onetake). A human recording keeps its room tone through the squeezed pauses
  (10 ms fades, no clicks). If the gate misreads a noisy room, pass `--thresh`.
