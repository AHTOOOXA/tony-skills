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

Three public indexes of Opus 5.5 videos with their prompts. Use them to find a reference for a style or a job,
to read how it was asked for, and to see how far a prompt reproduces. Read the post text too: the most-viewed
work often doesn't publish its prompt (on claudevideo.org, videos with a prompt have a median of ~450 views,
without one ~16k).

| Index | Best for | How to pull it |
|---|---|---|
| zhuyansen / jasonzhu.ai — ~1,400 posts with ≥ 5k views, ~370 with prompt text | views + bookmarks + prompt text + category + size in one file | `gh api repos/zhuyansen/jasonzhu.ai/contents/src/content/opus-prompts/cases.json -H "Accept: application/vnd.github.raw"` → `.cases[]`: `prompt.text` (null when unpublished), `stats.views`, `stats.bookmarks`, `category`, `video.width/height` |
| claudevideo.org — 1,276 videos | reach ranking and visual tags (`vertical`, `hand-drawn`, `product-ad`, `character-animation`…) | `curl https://claudevideo.org/wall.json` (index, no prompt text); the prompt is on `/videos/<slug>` between "THE PROMPT" and "MAKE ONE LIKE THIS"; ranked lists at `/videos/type/{product-ads,explainers,stories,motion-graphics}` |
| Skillry — 513 videos, each with a live remake | filter by aspect ratio and tech; compare original vs remake | `gh api repos/yihui-dev/awesome-opus5-5-videos/contents/data/videos.json -H "Accept: application/vnd.github.raw"`; page `skillry.dev/ai-videos/opus-5-5/<slug>`. No view counts; ~46 % of its "prompts" are just the post text |

Join them on the tweet id. Sort by views for ideas; by **bookmarks per view** for templates people reuse (the
one-shape film: 19.4k bookmarks on 933k views). What the remakes show: a look reproduces only when the prompt
pins it with numbers — canvas size, palette, line weight, frame rate of the drawing, a reference image; a
one-line prompt remakes into an unrelated film. When you borrow, borrow the grammar and the numbers, not the
content.

