# Tools, sources, licences

## When to use what

| Tool | Licence | Use when | Avoid when |
|---|---|---|---|
| **this skill's scripts** (bare HTML + `__seek` + Playwright + ffmpeg) | MIT | default: footage-heavy films, any brand, zero framework | — |
| claude-motion-design (howseen-ai) | MIT | pure motion films from brand assets; `analyze_song.py`, remake kit | — |
| onetake (feitangyuan) | **PolyForm Noncommercial** | learning: carry analysis, rhythm gates, 39 measured moves | any commercial product — reimplement ideas, never copy code |
| brag (latent-spaces) | MIT (check bundled music) | a 15–25 s launch teaser from a repo in one run (`/brag-slim` on Opus 5.5) | captured real-app flows |
| HyperFrames (HeyGen) | Apache-2.0 | 20 blueprints, GSAP timelines, `check` (contrast, caption zone, motion sidecars) | you want no dependencies |
| Remotion | free for individuals, company licence otherwise | React teams; `@remotion/transitions`, `@remotion/motion-blur` | motion blur renders audio N times (keep audio outside the blur) |
| ClaudeAnimationBase (JohnHeibel) | MIT | hand-drawn cartoon (p5.brush), character acting guide | product UI |
| image→video models (Kling, Veo, Seedance) | credits | social clips, soft 3D/clay looks | anything that must stay on-model |
| ElevenLabs SFX/Music, Stable Audio 3 | paid / open weights | bespoke foley and textures | free tiers for commercial work |

Opus picks bare HTML + `seek(t)` on its own; if you want a framework, say so. Effort: xhigh for a new film,
max when the first 3 s carry a launch, medium for fixes. Keep one session per brand — the renderer, sound
spec and QA get reused.

## Sources (the research behind this skill)

- Raphaël Aubry, "I made 10+ motion videos with Opus 5.5 in 3 days" (X article) + github.com/howseen-ai/claude-motion-design
- github.com/feitangyuan/onetake — carry score, rhythm gates, sound materials and one room, case verdicts
- github.com/latent-spaces/brag — reading floor, launch shape, cue scoring, SFX HF-risk analysis
- github.com/heygen-com/hyperframes — motion doctrine, cut catalogue, vertical layout, captions, audio diagnosis;
  James Russo (HeyGen), "HTML Is All Agents Need"
- github.com/JohnHeibel/ClaudeAnimationBase — ANIMATION_GUIDE (reads, timing, acting)
- @leomeethewoo "Make your product videos look expensive (Apple Framework)"; @twoclipping one-take launch film
  prompt; @motion_conquest Liquid Glass spec; @0xMovez "How to build motion design studio with Opus 5.5"
- TikTok Creative Center best practices and sound guidance; Meta Reels ads guide (safe zones, sound-off)
