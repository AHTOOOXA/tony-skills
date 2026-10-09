# Inspiration: what landed, and how it was asked for

The Opus 5.5 motion wave (late Sep 2026) produced a few films people actually shared. What they have in
common is not a process — it's **one clear idea, executed with conviction, usually cut to music**, with
real assets and the model given room to show off. Use these as starting points and as a bar to clear.

## The patterns

**1. The genre prompt — "show what you can do".** Four of the nine defining posts used one line:

> Make a dynamic 15-second motion graphics video that shows what an incredible motion designer you are,
> like it's your showreel for a résumé. go all out.

Why it works (0xMovez): "showreel for a résumé" names a genre the model already knows (fast cuts, a new
technique every shot, best work first); "what an incredible motion designer you are" makes the craft the
subject; "15-second" fits 6–8 shots in one pass; "go all out" is an effort multiplier on top of xhigh/max.
Weakness: "brief contagion" — hundreds of identical reels. It tests the engine, not the idea.

**2. The genre prompt pointed at a product (Tony Dinh, TypingMind — replaced a $1,000 agency video in 30 min):**

> Make a dynamic 15-second motion graphics video that shows what an incredible motion designer you are,
> like it's your showreel for a résumé. go all out. Make it a video to introduce http://typingmind.com.
> Use actual product screenshot/logo/assets. Must have music and motion must match the music.
> Do it like a real professional production video, not like a demo or prototype.

Three extra lines: the URL, real assets, music that drives the motion.

**3. One object becomes everything (@twoclipping, ~1M views).** An XML brief: `<inputs>` (8–12 UI states
the shape becomes, one accent colour, a ~120 BPM royalty-free song) → `<direction>` ("one shape, never cut —
it morphs size, radius and colour while its content swaps; a cursor drives every change; springs
everywhere, a tiny overshoot at most; the camera zooms so each state fills the frame") → `<structure>`
(a beat map: which state on which beat, the drop on the key visual) → `<gotchas>` → "show me the beat map
and 4 stills before the full film". The one-take launch film by the same author: everything is made out of
the previous thing, nothing fades or cuts; a flood colour clears the frame in 0.35 s on the drop.
His own verdict: "taste and direction is still lacking but the execution is pretty good" — the template
gives execution; the idea is still yours.

**4. A product launched as something absurdly bigger (Raphaël Aubry).** A baguette launched like a new
Apple product: white background, classical music, slow reverent camera, and four real recorded crunches
placed on their peaks. A K-pop comeback remade as a cut-paper zine: every lyric a ransom-note cut-out stamped
on the beat. Lesson: a strong, funny, specific premise + a real reference to remake + sound on the beat.
His harness: inputs → beat map (drop on the key visual) → 4 stills → full render → frame-by-frame check → audio.

**5. A mascot's tiny story, the app at the end (@jackfriks, 52k views):**

> use the pig assets … make a 9:16 short story animation with sound effects about the pig sending his
> partner love notes in the mailbox and make it fun and good, tease app at end

Story first, product last, made from the brand's existing art.

**6. One emotional metaphor (@Voxyz_ai, "small print").** Claude gets a pile of requests; it circles the
human part hidden inside them ("one hand. baby's asleep") and drops it into a jar; at night the words become
stars and join into a constellation. One HTML file, synthesized music, then a second-by-second polish pass
against the music. One feeling beats a feature list.

**7. A character with a voice (@achxvi, 8.9k likes).** The showreel line plus an ElevenLabs key: "make a
video where a character talks about the product". Voice + mascot is now what he sells as a service.

**8. A brand film whose inputs are ideas, not assets (@notdwd, 55 s).** The prompt asks for: one line of
what the brand becomes in 5 years (not today's features), one coined word the film should teach, and an
archival clip of the old way of doing it. Direction: "It sells one feeling and one idea, never features…
One hero object… the ONLY saturated colour in the film… The brand appears at the end, never before."
Structure: the old way as a cold open → the past at scale → the coined word taught → the hero object, the
music drops as its colour arrives → the line. Captions ≤ 7 words, one idea per shot.

**9. The pattern behind the saved posts (@guikyoki ranked 121 top Opus 5.5 motion posts by bookmarks).**
The showreel prompt "tests your setup, never your idea, because it does not contain one". What people
saved: a named reference film, then three storyboard directions that differ in their central picture, pick
one, a still per scene, then the render. Others outline the whole film and build one 6–8 s section for real
first.

## What they share

- **An idea you can say in one sentence.** Not "show the features".
- **Music drives the cut.** Beats for state changes, downbeats for big moments, the drop on the hero. (Or a
  voice, or one continuous camera move — something is the spine.)
- **Real assets.** The product's real screenshots/UI, logo, fonts, mascot art, brand lines.
- **Effort and freedom.** xhigh/max; "go all out"; few constraints on taste.
- **The model looks at its own frames.** Stills and sheets, then fixes. That loop is the difference between
  the "mid" first try and the shared ones.
- **Sound placed on the picture** — real crunches on their peaks, a sting on the drop.

## Where the bar is

The slop look: centred title on a gradient, everything fading in, a logo at the end, the same move on every
element, a vague headline. If your film could be any brand's, push the idea further.

## Pulling a reference from the galleries

Three public indexes collect AI-made videos from X with their stats and, where the author published one,
the prompt. `scripts/refs.py` joins them on the tweet id into one local file
(`~/.cache/motion-video/refs.json`, about 2,350 posts, about 780 with a real prompt) that you can search
in a second. Use it to find a reference for a style or a job, read how it was asked for, and see how far a
prompt actually reproduces.

```bash
python3 $S/scripts/refs.py search "line art" --has-prompt --sort saves-per-view   # templates people reuse
python3 $S/scripts/refs.py search --aspect 9:16 --tag product-ad --sort views       # what reached people
python3 $S/scripts/refs.py search product launch --has-prompt -n 5 --full           # read the briefs
python3 $S/scripts/refs.py search --tech three.js --category explainer --sort saves
python3 $S/scripts/refs.py show 2103273003555402193        # one post: stats, size, every prompt we have
python3 $S/scripts/refs.py facets                          # the tags, categories and tech you can filter on
python3 $S/scripts/refs.py update --fetch-prompts 200      # refresh; also pull prompts from claudevideo pages
```

Search words match title, summary, tags, post text and prompts in any language. Matches in the title,
summary or tags come first and matches only inside a long prompt come last, with a header between the
groups. The cache refreshes itself after 14 days. `--has-prompt` means a real brief rather than a caption.
Each hit shows views, saves, saves per view, author, aspect and length, the first line of the prompt and
the post URL.

| Index | What it adds to the join | Caveats |
|---|---|---|
| zhuyansen / jasonzhu.ai: ~1,430 posts with ≥ 5k views | views and bookmarks, video size and length, a curated prompt (often found in the author's reply), category, tools, an English summary | only posts above 5k views; about a quarter have a prompt |
| claudevideo.org: ~1,280 videos | visual tags (`vertical`, `hand-drawn`, `product-ad`, `kinetic-type`…), theme, post text, small posts too | the index has no prompt text, so `update --fetch-prompts N` reads it from `/videos/<slug>` (cached per slug) |
| Skillry: ~510 videos, each with a live remake | tech tags (`canvas`, `threejs`, `gsap`, `shader`…), a remake page | no stats; ~46 % of its "prompts" are only the post text (flagged `post text`, so `--has-prompt` skips them) |

What the data says:

- **The most-viewed work often hides its prompt.** 61 of the 100 most-viewed posts publish no usable
  prompt. On claudevideo.org the median video with a prompt has ~450 views and the median video without
  one has ~16k. Read the post and the author's replies, and look at the frames.
- **Sort by views for ideas, and by saves per view for templates people reuse.** The one-shape UI film
  has 20k bookmarks on 1.0M views (1.9 %). The typical viral showreel sits at 0.3–0.8 %. `saves-per-view`
  ignores posts under 5k views, because their ratios are noise.
- **Remakes reproduce only what the prompt pins with numbers**: canvas size, palette hex, line weight,
  the frame rate of the drawing, a reference image. On Skillry, a one-line prompt remakes into an
  unrelated film. The showreel one-liner, copied verbatim to test consistency, came back as a Bauhaus
  grid (@zaqailo).
- **Borrow the grammar and the numbers, not the content.** Take the structure of a brief (`<inputs>` →
  `<direction>` → `<structure>` → `<gotchas>`), its banned list, its beat map. Leave behind its brand,
  its story and its assets.
- Before you write `style_guide.md` from a reference, measure it (`story.md`, "Reference-driven style").
- The numbers are snapshots (stats checked early October 2026), and attribution is the creator's own
  claim. Some posts are model-vs-model comparisons (`--category comparison`); filter them out when you
  want films.
