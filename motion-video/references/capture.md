# Capturing a real app (`scripts/capture.mjs`)

Real UI only: never redraw or reconstruct the product from imagination — viewers and owners notice, and it
"ruins the impression". If the state you need is gone (an old design for a before/after), deploy that
version somewhere and film it.

## How it works

- **Slowed page clock** (`slow: 4`): `performance.now`, `Date.now`, timers, `requestAnimationFrame` and every
  CSS/WAAPI animation (CDP `Animation.setPlaybackRate`) run 4× slower. A screenshot loop runs as fast as it
  can; frames are stamped in APP time. 4× gives 75–100 effective fps from a 30–60 ms screenshot.
- **Device pixels**: a 432×768 viewport at `scale: 2.5` → 1080×1920 frames. CDP screencast is capped at CSS
  pixels, so it's a `captureScreenshot` loop with `captureBeyondViewport` and a clip that follows the scroll
  offset (otherwise mid-scroll frames come back blank).
- **Marks**: `s.mark('tap')` stamps a named moment; the composition builds its timeline from marks, so
  re-recording a take never breaks the edit.
- **Speed ramps** are done in the composition, not the take: map take-time → video-time piecewise
  (`[from, to, speed]`), 3–3.5× over dead spans (a page change's near-black gap, a loading wait, an ignored tap).

## Getting a clean, repeatable take

- **Same data every take**: `mocks: [{url: '**/api/draw**', body: {...}}]` for random endpoints; record one real
  streaming LLM response once and replay it with `stream: {match, lines, gapMs}`.
- **Drive it like a finger**: `s.tap(locator)` draws a soft touch mark first; poll app state and retry taps
  that land mid-animation; navigate in-app (router links) while recording — a full page load can hang.
- **Smooth scroll**: native smooth scrolling ignores the slowed clock; `s.glideTo(locator, 0.4, 1200)` glides the
  right scroll container so the element sits at 40 % of the viewport.
- **Privacy**: `hide: [selectors]` for real avatars, names, dev banners, debug gears (eruda); curate history
  lists by hand. A public video must not show a real person's data.
- **Log in / platform mocks** in `init` (runs before app code): localStorage flags, a mock user.
- Fonts: the app's own; if a webfont subset is lazy-loaded, warm it before `start()`.

## Using takes in the composition

`take.json` = `{frames: [{file, t(ms)}], marks: [{label, t}]}`. In `__seek`, pick the frame for take-time with
`frameAt(take, ms)` (template) and show it full-bleed (no device frames unless the brief asks — a phone mockup
reads as an ad template). Overlays (labels, clock, stickers) need a placement pass per screen.
A dead-still hold on the last footage frame (+0.8 s) gives a payoff label time to be read.
