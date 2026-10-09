#!/usr/bin/env node
// motion-video · qa/probe.mjs — check framing, speed and continuity from the DOM, without rendering a pixel.
//
// Loads the composition like render.mjs, seeks through the timeline and reads element boxes
// (getBoundingClientRect: after every transform, the camera's included). Default: every frame at the
// film's fps (a seek costs a few ms, so a 30 s film takes seconds); --hz 10 for a quicker, coarser pass
// (it can miss the peak of a 0.2 s slam). Run it before every render.
//
//   node probe.mjs comp.html [--hz N (default: fps)] [--fps 30] [--max-px 80] [--track '#a,.b'] [--safe x0,y0,x1,y1] [--query format=wide]
//
// frame   window.__meta.inFrame = ['#logo', {sel: '#cta', area: 'safe', from: 4, to: 6}, ['#title', 'safe'], …]
//         Each matched, visible element (opacity > .05) must stay wholly inside the frame (default) or the
//         safe area (__meta.safe = {x0, y0, x1, y1}, or --safe). Reports spans and how far out, per side.
//         A selector that never matches anything is a violation too (a typo would otherwise pass).
// speed   Centre travel of each tracked element over ONE frame at the film's fps (t → t + 1/fps), in px.
//         Over --max-px (80, scaled to the frame's long edge / 1920) outside the __meta.blur windows it
//         strobes: blur that span or slow the move. Inside a blur window it's listed as fine. Tracked:
//         __meta.track or --track selectors, else every positioned/transformed visible element (ground
//         layers covering ≥ 85 % of the frame are skipped; a child flagged together with its flagged
//         ancestor is folded into it). Pairs that straddle a cut are skipped.
// cuts    Info only: for each __meta.cuts time, what persists across it (same element, same text/image,
//         visible on both sides) — a carry when it moves or scales, an anchor when it holds still — vs a
//         hard swap where nothing survives.
//
// Exit: 0 clean, 1 violations (frame / speed / seek errors), 2 could not load.
import { existsSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const comp = args.find(a => !a.startsWith('-') && /\.html?$/.test(a));
if (!comp) { console.error("usage: node probe.mjs comp.html [--hz 10] [--fps 30] [--max-px 80] [--track '#a,.b'] [--safe x0,y0,x1,y1] [--query format=wide]"); process.exit(2); }
const hzArg = Number(opt('--hz', 0));
const MAXPX = Number(opt('--max-px', 80));
const query = opt('--query', '');

async function loadPlaywright() {
  for (const base of [process.cwd(), path.dirname(path.resolve(comp))]) {
    const req = createRequire(path.join(base, 'noop.js'));
    for (const name of ['playwright', 'playwright-core']) {
      try { return await import(pathToFileURL(req.resolve(name)).href); } catch {}
    }
  }
  for (let dir = process.cwd(); dir !== path.dirname(dir); dir = path.dirname(dir)) {
    const store = path.join(dir, 'node_modules/.pnpm');
    if (!existsSync(store)) continue;
    const pkg = readdirSync(store).filter(d => d.startsWith('playwright-core@')).sort().pop();
    if (pkg) return import(pathToFileURL(path.join(store, pkg, 'node_modules/playwright-core/index.mjs')).href);
  }
  console.error('Playwright not found. Run: npm i -D playwright && npx playwright install chromium');
  process.exit(2);
}

// Runs in the page: seek to t, then read boxes. Same seek as render.mjs minus the paint wait (layout is synchronous).
async function sampleInPage({ t, inFrame, track, all }) {
  await window.__seek(t);
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
  const VW = innerWidth, VH = innerHeight, memo = new Map();
  const opac = el => {
    if (!el || el.nodeType !== 1) return 1;
    if (memo.has(el)) return memo.get(el);
    const cs = getComputedStyle(el);
    let o = cs.display === 'none' || cs.visibility === 'hidden' ? 0 : parseFloat(cs.opacity);
    if (o > 0) o *= opac(el.parentElement);
    memo.set(el, o); return o;
  };
  const pathOf = el => {
    const parts = [];
    for (let e = el; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
      let p = e.tagName.toLowerCase();
      if (e.id) p += '#' + e.id;
      else {
        const sib = e.parentElement ? [...e.parentElement.children].filter(x => x.tagName === e.tagName) : [];
        if (e.classList.length) p += '.' + e.classList[0];
        if (sib.length > 1) p += ':' + sib.indexOf(e);
      }
      parts.unshift(p);
    }
    return parts.join('>');
  };
  const keyOf = el => {
    if (el.tagName === 'IMG' || el.tagName === 'VIDEO') return (el.currentSrc || el.src || '').split('/').pop().replace(/\d{2,}(?=\.\w+$)/, '#');
    let own = ''; for (const n of el.childNodes) if (n.nodeType === 3) own += n.textContent;
    return own.trim().slice(0, 30);
  };
  const box = el => { const r = el.getBoundingClientRect(); return { x0: r.left, y0: r.top, x1: r.right, y1: r.bottom }; };
  const meet = (a, b) => ({ x0: Math.max(a.x0, b.x0), y0: Math.max(a.y0, b.y0), x1: Math.min(a.x1, b.x1), y1: Math.min(a.y1, b.y1) });
  const clips = new Map(), VIEW = { x0: 0, y0: 0, x1: VW, y1: VH };
  const clipOf = p => {                                    // the region p's descendants are clipped to (masks, viewport)
    if (!p || p === document.body || p === document.documentElement) return VIEW;
    if (clips.has(p)) return clips.get(p);
    const cs = getComputedStyle(p), up = clipOf(p.parentElement);
    const c = cs.overflowX !== 'visible' || cs.overflowY !== 'visible' || cs.clipPath !== 'none' ? meet(up, box(p)) : up;
    clips.set(p, c); return c;
  };
  const paints = (el, key) => {
    if (key || /^(IMG|VIDEO|CANVAS|svg)$/.test(el.tagName)) return true;
    const cs = getComputedStyle(el);
    return !/^(rgba\(0, 0, 0, 0\)|transparent)$/.test(cs.backgroundColor) || cs.backgroundImage !== 'none' || parseFloat(cs.borderTopWidth) > 0 || cs.boxShadow !== 'none';
  };

  const frame = inFrame.map(({ sel }) => [...document.querySelectorAll(sel)].map(el => ({ ...box(el), op: opac(el) })));

  const els = track ? track.flatMap(s => [...document.querySelectorAll(s)]) : [...document.body.querySelectorAll('*')].filter(el => {
    const tag = el.tagName.toLowerCase();
    if (['script', 'style', 'link', 'template', 'br'].includes(tag) || (tag !== 'svg' && el.closest('svg'))) return false;
    if (all) return true;
    const cs = getComputedStyle(el);
    return cs.position === 'absolute' || cs.position === 'fixed' || cs.transform !== 'none' || tag === 'img' || tag === 'video' || tag === 'canvas' || tag === 'svg';
  });
  const boxes = [];
  for (const el of els) {
    const b = box(el), w = b.x1 - b.x0, h = b.y1 - b.y0, op = opac(el);
    if (w < 2 || h < 2 || op < 0.05) continue;
    if (!track && w * h >= 0.85 * VW * VH) continue;                         // ground: backgrounds, camera layers
    const v = meet(b, clipOf(el.parentElement)), vis = Math.max(0, v.x1 - v.x0) * Math.max(0, v.y1 - v.y0);
    const key = keyOf(el);
    if (all && !paints(el, key)) continue;                                   // layout wrappers don't carry anything
    boxes.push({ id: pathOf(el), key, cx: (b.x0 + b.x1) / 2, cy: (b.y0 + b.y1) / 2, w, h, area: w * h, vis, on: vis > 0 });
  }
  return { frame, boxes };
}

const pw = await loadPlaywright();
const chromium = pw.chromium ?? pw.default?.chromium; // CJS builds expose it only on default
const CHROME = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium'].find(p => existsSync(p));
const browser = await chromium.launch({ ...(CHROME ? { executablePath: CHROME } : {}), headless: true,
  args: ['--allow-file-access-from-files', '--disable-threaded-animation', '--hide-scrollbars'] });
const url = pathToFileURL(path.resolve(comp)).href + (query ? '?' + query.replace(/^\?/, '') : '');
const errors = [];
let meta;
try {
  const first = await browser.newPage();
  await first.goto(url);
  await first.evaluate(() => window.__ready);
  meta = await first.evaluate(() => window.__meta);
  await first.close();
  if (!meta?.duration || !meta.width || !meta.height) throw new Error('window.__meta needs duration, width, height');
} catch (e) { console.error(`could not load ${comp}: ${e.message.split('\n')[0]}`); await browser.close(); process.exit(2); }
const page = await browser.newPage({ viewport: { width: meta.width, height: meta.height } });
page.on('pageerror', e => errors.push(`pageerror: ${e.message.split('\n')[0]}`));
await page.goto(url);
await page.evaluate(() => window.__ready);
await page.addStyleTag({ content: '*,*::before,*::after{transition:none!important}' });

const FPS = Number(opt('--fps', 0)) || meta.fps || 30;
const HZ = hzArg || FPS;
const W = meta.width, H = meta.height, LIMIT = MAXPX * Math.max(W, H) / 1920;
const blur = meta.blur ?? [], cuts = meta.cuts ?? [];
const safeArg = opt('--safe', null)?.split(',').map(Number);
const safe = safeArg ? { x0: safeArg[0], y0: safeArg[1], x1: safeArg[2], y1: safeArg[3] } : meta.safe ?? null;
const inFrame = (meta.inFrame ?? []).map(e => typeof e === 'string' ? { sel: e } : Array.isArray(e) ? { sel: e[0], area: e[1] } : e)
  .map(e => ({ sel: e.sel, area: e.area ?? 'frame', from: e.from ?? 0, to: e.to ?? meta.duration }));
const trackArg = opt('--track', null);
const track = trackArg ? trackArg.split(',').map(s => s.trim()) : meta.track ?? null;
if (inFrame.some(e => e.area === 'safe') && !safe) { console.error("inFrame asks for 'safe' but there is no __meta.safe = {x0, y0, x1, y1} (or --safe)"); await browser.close(); process.exit(2); }

const fmt = t => t.toFixed(2);
const cache = new Map();                                    // at --hz = fps, t + 1/fps is the next sample
const sample = async (t, all = false) => {
  const key = t.toFixed(5) + all;
  if (cache.has(key)) return cache.get(key);
  let r = null;
  try { r = await page.evaluate(sampleInPage, { t, inFrame, track: all ? null : track, all }); }
  catch (e) { errors.push(`__seek(${fmt(t)}) threw: ${e.message.split('\n')[0]}`); }
  if (cache.size > 4) cache.delete(cache.keys().next().value);
  cache.set(key, r); return r;
};
const inBlur = (a, b) => blur.some(([x, y]) => b >= x && a <= y);
const crossesCut = (a, b) => cuts.some(c => a < c && b >= c);
const ancestorIn = (id, set) => { for (let i = id.lastIndexOf('>'); i > 0; i = id.lastIndexOf('>', i - 1)) if (set.has(id.slice(0, i))) return true; return false; };
const short = id => { const s = id.split('>'); let i = s.length - 1; while (i > 0 && !s[i].includes('#')) i--; return s.slice(Math.max(i, s.length - 3)).join('>'); };

// Spans: consecutive flagged sample indices per key.
const spans = new Map();
const flag = (key, i, t, v, extra = {}) => {
  const list = spans.get(key) ?? spans.set(key, []).get(key), last = list.at(-1);
  if (last && last.i1 === i - 1) { last.i1 = i; last.t1 = t; if (v > last.peak) Object.assign(last, { peak: v, at: t }, extra); }
  else list.push({ i0: i, i1: i, t0: t, t1: t, peak: v, at: t, ...extra });
};

const N = Math.floor(meta.duration * HZ - 1e-9);
const matched = inFrame.map(() => false);
const t0 = Date.now();
for (let i = 0; i <= N; i++) {
  const t = Math.min(i / HZ, meta.duration - 1 / FPS);
  const a = await sample(t);
  if (!a) continue;
  // frame
  a.frame.forEach((els, k) => {
    const e = inFrame[k];
    if (els.length) matched[k] = true;
    if (t < e.from || t > e.to) return;
    const A = e.area === 'safe' ? safe : { x0: 0, y0: 0, x1: W, y1: H };
    els.forEach((b, n) => {
      if (b.op < 0.05 || b.x1 - b.x0 < 1) return;
      const out = { left: A.x0 - b.x0, right: b.x1 - A.x1, top: A.y0 - b.y0, bottom: b.y1 - A.y1 };
      const [side, px] = Object.entries(out).sort((p, q) => q[1] - p[1])[0];
      if (px > 0.5) flag(`frame|${e.sel}${els.length > 1 ? `[${n}]` : ''}|${e.area}`, i, t, px, { side });
    });
  });
  // speed: one frame ahead
  const t2 = t + 1 / FPS;
  if (crossesCut(t, t2) || t2 > meta.duration) continue;
  const b = await sample(t2);
  if (!b) continue;
  const prev = new Map(a.boxes.map(x => [x.id, x]));
  const fast = new Map();
  for (const x of b.boxes) {
    const p = prev.get(x.id);
    if (!p || !(p.on || x.on)) continue;                       // off frame on both sides: can't strobe
    const d = Math.hypot(x.cx - p.cx, x.cy - p.cy);
    if (d > LIMIT) fast.set(x.id, d);
  }
  const ids = new Set(fast.keys());
  for (const [id, d] of fast) if (!ancestorIn(id, ids)) flag(`speed|${id}|${inBlur(t, t2) ? 'blur' : 'sharp'}`, i, t, d);
}

// cuts: what survives each hard cut
const cutInfo = [];
for (const c of cuts) {
  const a = await sample(Math.max(0, c - 1 / FPS), true), b = await sample(c, true);
  if (!a || !b) continue;
  const minArea = 0.002 * W * H;
  const before = new Map(a.boxes.filter(x => x.vis >= minArea).map(x => [x.id, x]));
  const after = b.boxes.filter(x => x.vis >= minArea);
  const kept = after.filter(x => before.get(x.id)?.key === x.key).map(x => {
    const p = before.get(x.id), moved = Math.hypot(x.cx - p.cx, x.cy - p.cy), scaled = Math.abs(Math.sqrt(x.area / p.area) - 1);
    return { id: x.id, how: moved > 2 || scaled > 0.01 ? `moves ${moved.toFixed(0)} px${scaled > 0.01 ? `, scale ×${Math.sqrt(x.area / p.area).toFixed(2)}` : ''}` : 'still' };
  });
  const ids = new Set(kept.map(k => k.id));
  const top = kept.filter(k => !ancestorIn(k.id, ids)).sort((p, q) => (p.how === 'still') - (q.how === 'still'));
  cutInfo.push({ c, n0: before.size, n1: after.length, top });
}
await browser.close();

// report
const lines = [];
let fails = 0;
for (const [key, list] of spans) {
  const [kind, id, mode] = key.split('|');
  for (const s of list) {
    const when = s.t0 === s.t1 ? `${fmt(s.t0)} s` : `${fmt(s.t0)}–${fmt(s.t1)} s`;
    if (kind === 'frame') { fails++; lines.push([s.peak, `frame  FAIL  ${id}  ${when}  out by ${s.peak.toFixed(0)} px ${s.side} of the ${mode} (worst ${fmt(s.at)} s)`]); }
    else if (mode === 'sharp') { fails++; lines.push([s.peak, `speed  FAIL  ${short(id)}  ${when}  ${s.peak.toFixed(0)} px/frame @ ${FPS} fps (${fmt(s.at)} s), limit ${LIMIT.toFixed(0)} — strobes: slow it or blur [${fmt(Math.max(0, s.t0 - 0.1))}, ${fmt(s.t1 + 1 / HZ + 0.1)}]`]); }
    else lines.push([-1, `speed  ok    ${short(id)}  ${when}  ${s.peak.toFixed(0)} px/frame, inside a blur window`]);
  }
}
inFrame.forEach((e, k) => { if (!matched[k]) { fails++; lines.push([Infinity, `frame  FAIL  ${e.sel}  matched nothing at any sampled time`]); } });
for (const e of errors) { fails++; lines.push([Infinity, `error  ${e}`]); }

console.log(`probe ${path.basename(comp)}  ${meta.duration} s · ${W}×${H} · ${N + 1} samples @ ${HZ} Hz · speed at ${FPS} fps, limit ${LIMIT.toFixed(0)} px/frame · ${((Date.now() - t0) / 1000).toFixed(1)} s`);
if (!inFrame.length) console.log("frame  skip  (declare __meta.inFrame = ['#logo', {sel: '#cta', area: 'safe'}] to check what must stay in frame)");
const MAX = 12;
const sorted = lines.sort((p, q) => q[0] - p[0]).map(l => l[1]);
for (const l of sorted.slice(0, MAX)) console.log(l);
if (sorted.length > MAX) console.log(`…  ${sorted.length - MAX} more`);
for (const { c, n0, n1, top } of cutInfo) {
  const what = top.length ? `${top.some(k => k.how !== 'still') ? 'carried' : 'anchored'}: ${top.slice(0, 3).map(k => `${short(k.id)} (${k.how})`).join(', ')}${top.length > 3 ? ` +${top.length - 3}` : ''}`
    : `hard swap — nothing persists (painted elements: ${n0} before, ${n1} after)`;
  console.log(`cut    info  ${fmt(c)} s  ${what}`);
}
console.log(fails ? `→ ${fails} violation${fails > 1 ? 's' : ''}` : '→ clean');
process.exit(fails ? 1 : 0);
