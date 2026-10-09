// motion-video · capture.mjs — record a REAL app (web app, site, Mini App in a browser) as frames.
//
// Real-time capture is choppy (a screenshot takes 30–60 ms). So the page's clock is slowed SLOW×
// (timers, rAF, performance.now, Date.now and every CSS/WAAPI animation via CDP), frames are taken
// as fast as possible and stamped in APP time. A 4× slow clock gives 75–100 effective fps.
// The composition then picks frames by take-time (templates/compose.html → frameAt()).
//
//   import { openStage } from './capture.mjs';
//   const s = await openStage({ base: 'http://localhost:5173', viewport: [432, 768], scale: 2.5, out: '.video/takes' });
//   await s.goto('/');                    // navigate at full speed (not recorded)
//   await s.start('main');                // start recording take "main"
//   s.mark('home');                       // marks = named moments, in app time → drive your timeline
//   await s.glideTo('text=Pricing', 0.4, 1200);  // smooth scroll so the element sits at 40% of the viewport
//   await s.tap(s.page.getByText('Start'));      // finger: a soft touch mark, then a click
//   await s.wait(800);                    // wait in APP time
//   await s.stop();                       // writes takes/main/take.json { frames:[{file,t}], marks:[{label,t}] }
//   await s.close();
//
// Options: mocks [{url, body}] (fix random/LLM endpoints so every take shows the same data),
// stream {match, lines, gapMs} (replay a recorded streaming response line by line),
// init (a function run in the page before app code: log in, set localStorage, hide debug UI),
// hide (CSS selectors to hide: dev banners, debug gears, real avatars — keep private data out).
import { mkdirSync, rmSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

async function loadPlaywright() {
  const req = createRequire(path.join(process.cwd(), 'noop.js'));
  for (const name of ['playwright', 'playwright-core']) { try { return await import(pathToFileURL(req.resolve(name)).href); } catch {} }
  for (let dir = process.cwd(); dir !== path.dirname(dir); dir = path.dirname(dir)) {
    const store = path.join(dir, 'node_modules/.pnpm');
    if (!existsSync(store)) continue;
    const pkg = readdirSync(store).filter(d => d.startsWith('playwright-core@')).sort().pop();
    if (pkg) return import(pathToFileURL(path.join(store, pkg, 'node_modules/playwright-core/index.mjs')).href);
  }
  throw new Error('Playwright not found: npm i -D playwright && npx playwright install chromium');
}

/** Runs in the page before any app code. */
function pageSetup({ slow, stream, hide }) {
  const S = slow;
  const rNow = performance.now.bind(performance), t0 = rNow();
  const rDateNow = Date.now, d0 = rDateNow();
  const warp = t => t0 + (t - t0) / S;
  performance.now = () => warp(rNow());
  Date.now = () => d0 + (rDateNow() - d0) / S;
  const rST = window.setTimeout.bind(window), rSI = window.setInterval.bind(window);
  window.setTimeout = (fn, ms = 0, ...a) => rST(fn, (Number(ms) || 0) * S, ...a);
  window.setInterval = (fn, ms = 0, ...a) => rSI(fn, (Number(ms) || 0) * S, ...a);
  const rRAF = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = cb => rRAF(ts => cb(warp(ts)));

  // Native smooth scrolling ignores the page clock: replace it with an eased glide on the slowed clock.
  const ease = t => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
  window.__glide = (target, top, ms) => {
    const isWin = target === window, from = isWin ? window.scrollY : target.scrollTop, start = performance.now();
    const id = (window.__glideId = (window.__glideId ?? 0) + 1);
    const step = () => {
      if (id !== window.__glideId) return;
      const k = Math.min(1, (performance.now() - start) / ms), y = from + (top - from) * ease(k);
      if (isWin) window.__rScrollTo(0, y); else target.scrollTop = y;
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  window.__rScrollTo = window.scrollTo.bind(window);
  for (const [proto, isWin] of [[window, true], [Element.prototype, false]]) {
    const rTo = proto.scrollTo, rBy = proto.scrollBy;
    proto.scrollTo = function (a, b) { return a?.behavior === 'smooth' ? window.__glide(isWin ? window : this, a.top ?? 0, 520) : rTo.call(this, a, b); };
    proto.scrollBy = function (a, b) {
      if (a?.behavior !== 'smooth') return rBy.call(this, a, b);
      const cur = isWin ? window.scrollY : this.scrollTop;
      return window.__glide(isWin ? window : this, cur + (a.top ?? 0), 520);
    };
  }
  window.__scroller = el => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const { overflowY } = getComputedStyle(p);
      if ((overflowY === 'auto' || overflowY === 'scroll') && p.scrollHeight > p.clientHeight) return p;
    }
    return window;
  };
  window.__glideTo = (el, frac, ms) => {
    const sc = window.__scroller(el), cur = sc === window ? window.scrollY : sc.scrollTop;
    const viewTop = sc === window ? 0 : sc.getBoundingClientRect().top, viewH = sc === window ? innerHeight : sc.clientHeight;
    const r = el.getBoundingClientRect();
    window.__glide(sc, cur + (r.top + r.height / 2 - viewTop) - viewH * frac, ms);
  };

  // Replay a recorded streaming response (NDJSON/SSE lines) at a steady pace.
  if (stream) {
    const rFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : input.url;
      if (!url.includes(stream.match)) return rFetch(input, init);
      const enc = new TextEncoder();
      const body = new ReadableStream({ async start(c) {
        for (const line of stream.lines) { await new Promise(r => setTimeout(r, stream.gapMs)); c.enqueue(enc.encode(line + '\n')); }
        c.close();
      } });
      return new Response(body, { status: 200, headers: { 'content-type': stream.type ?? 'application/x-ndjson' } });
    };
  }

  addEventListener('DOMContentLoaded', () => {
    const st = document.createElement('style');
    st.textContent = `.mv-touch{position:fixed;z-index:2147483647;width:56px;height:56px;margin:-28px 0 0 -28px;border-radius:50%;
      background:rgb(255 255 255/.32);box-shadow:0 0 0 2px rgb(255 255 255/.5);pointer-events:none}
      html{scroll-behavior:auto!important} ${hide.length ? hide.join(',') + '{visibility:hidden!important}' : ''}`;
    document.head.append(st);
  });
  window.__touch = (x, y) => {
    const d = document.createElement('div');
    d.className = 'mv-touch'; d.style.left = x + 'px'; d.style.top = y + 'px';
    document.body.append(d);
    d.animate([{ transform: 'scale(.55)', opacity: 0 }, { transform: 'scale(.9)', opacity: 1, offset: 0.25 }, { transform: 'scale(1.25)', opacity: 0 }],
      { duration: 460, easing: 'ease-out' }).finished.then(() => d.remove());
  };
}

export async function openStage({ base, viewport = [432, 768], scale = 2.5, slow = 4, out = '.video/takes', locale = 'en-US',
  mocks = [], stream = null, init = null, hide = [], mobile = true, chrome = null } = {}) {
  const pw = await loadPlaywright(); const chromium = pw.chromium ?? pw.default?.chromium; // CJS builds: only on default
  const exe = chrome ?? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome'].find(p => existsSync(p));
  const browser = await chromium.launch({ ...(exe ? { executablePath: exe } : {}), headless: true,
    args: ['--run-all-compositor-stages-before-draw', '--disable-new-content-rendering-timeout', '--disable-threaded-animation', '--disable-checker-imaging'] });
  const [vw, vh] = viewport;
  const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: scale, isMobile: mobile, hasTouch: mobile, locale, ignoreHTTPSErrors: true });
  if (init) await ctx.addInitScript(init);
  await ctx.addInitScript(pageSetup, { slow, stream, hide });
  for (const m of mocks) await ctx.route(m.url, r => r.fulfill({ status: 200, contentType: 'application/json', body: typeof m.body === 'string' ? m.body : JSON.stringify(m.body) }));
  const page = await ctx.newPage();
  const logs = [];
  page.on('pageerror', e => logs.push('pageerror: ' + e.message.slice(0, 200)));
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Animation.enable');

  // Recording: a screenshot loop at full device pixels (CDP screencast is capped at CSS pixels).
  // captureBeyondViewport + a clip that follows the scroll offset, or mid-scroll frames come back blank.
  let frames = [], rec = null, idx = 0, dir = '', loop = null;
  async function shootLoop() {
    while (rec) {
      const a = Date.now();
      const { cssLayoutViewport: v } = await cdp.send('Page.getLayoutMetrics').catch(() => ({ cssLayoutViewport: { pageX: 0, pageY: 0 } }));
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 95, captureBeyondViewport: true,
        clip: { x: v.pageX, y: v.pageY, width: vw, height: vh, scale } }).catch(() => ({}));
      const b = Date.now();
      if (!data || !rec) continue;
      const file = `f${String(idx++).padStart(5, '0')}.jpg`;
      writeFileSync(path.join(dir, file), Buffer.from(data, 'base64'));
      frames.push({ file, wall: (a + b) / 2000 });
    }
  }

  const s = {
    page, cdp, logs,
    /** Wait `ms` of APP time. */
    wait: ms => page.waitForTimeout(ms * slow),
    /** Navigate at full speed (not recorded), then slow the page's animations. Prefer in-app navigation while recording. */
    async goto(p) {
      await cdp.send('Animation.setPlaybackRate', { playbackRate: 1 });
      await page.goto(base + p, { waitUntil: 'networkidle' });
      await cdp.send('Animation.setPlaybackRate', { playbackRate: 1 / slow });
    },
    async start(name) {
      dir = path.join(path.resolve(out), name);
      rmSync(dir, { recursive: true, force: true });
      mkdirSync(dir, { recursive: true });
      frames = []; idx = 0; rec = { name, marks: [], t0: Date.now() / 1000 };
      await cdp.send('Animation.setPlaybackRate', { playbackRate: 1 / slow });
      loop = shootLoop();
    },
    /** A named moment (in app time). Pass `wall` to stamp a moment you captured earlier. */
    mark(label, wall = Date.now() / 1000) { rec.marks.push({ label, wall }); },
    /** Tap like a finger: a soft touch mark, a beat, then a click at the element's centre. */
    async tap(locator, { dx = 0, dy = 0 } = {}) {
      const b = await locator.boundingBox();
      const x = b.x + b.width / 2 + dx, y = b.y + b.height / 2 + dy;
      await page.evaluate(([x, y]) => window.__touch(x, y), [x, y]);
      await s.wait(90);
      await page.mouse.click(x, y);
    },
    /** Smoothly scroll the element's scroller so the element sits at `frac` of the viewport height. */
    glideTo: (selectorOrLocator, frac = 0.4, ms = 1200) =>
      (typeof selectorOrLocator === 'string' ? page.locator(selectorOrLocator).first() : selectorOrLocator)
        .evaluate((el, [f, m]) => window.__glideTo(el, f, m), [frac, ms]),
    /** Type like a person: per-character delays on the slowed clock. */
    async type(locator, text, cps = 14) { await locator.click(); for (const ch of text) { await page.keyboard.type(ch); await s.wait(1000 / cps); } },
    async stop() {
      await page.waitForTimeout(300);
      const { t0, marks, name } = rec;
      rec = null;
      await loop;
      const toApp = w => ((w - t0) * 1000) / slow;
      const meta = { name, slow, scale, viewport, frames: frames.map(f => ({ file: f.file, t: Math.max(0, toApp(f.wall)) })),
        marks: marks.map(m => ({ label: m.label, t: toApp(m.wall) })) };
      writeFileSync(path.join(dir, 'take.json'), JSON.stringify(meta, null, 1));
      const dur = meta.frames.at(-1)?.t ?? 0;
      console.log(`take ${name}: ${frames.length} frames over ${(dur / 1000).toFixed(2)} s app time → ${(frames.length / (dur / 1000)).toFixed(0)} fps`);
      return meta;
    },
    close: () => browser.close(),
  };
  return s;
}
