#!/usr/bin/env node
// motion-video · render.mjs — render a composition frame by frame and encode a clean MP4.
//
// The composition is any HTML page that exposes (see templates/compose.html):
//   window.__meta = { duration, fps?, width, height, blur?: [[t0, t1], …], cuts?: [t, …] }
//   window.__seek(t)  → paints the exact frame for time t (seconds); may return a Promise
//   window.__ready    → optional Promise resolved when fonts/images are loaded
//
//   node render.mjs comp.html -o out.mp4 [--audio mix.wav] [--fps 30] [--ss 2] [--sub 10]
//   node render.mjs comp.html --stills 0,1.5,3.2 -o stills/      (PNG stills, blur included)
//   node render.mjs comp.html --draft -o draft.mp4               (half size, no blur, fast)
//
// What it does right that a naive screenshot loop gets wrong:
//  · PNG frames (no JPEG chroma loss), encoded as limited-range BT.709 with correct colour tags.
//    A plain RGB→YUV in ffmpeg uses BT.601 and full range: reds and purples shift, blacks lift.
//  · Motion blur only where something moves fast (__meta.blur windows): SUB sub-frames over a
//    180° shutter, averaged in LINEAR light (sRGB averaging darkens bright edges as they smear),
//    never across a hard cut (__meta.cuts) — blending two shots makes mud.
//  · Optional supersampling (--ss 2): render at 2× device pixels, Lanczos down — sharper type.
//  · Static fine grain added at encode (--grain 3) so dark gradients don't band after platform re-encodes.
//  · Fast capture via CDP (optimizeForSpeed) and parallel workers (--workers N).
import { mkdirSync, rmSync, existsSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import os from 'node:os';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const flag = k => args.includes(k);
const comp = args.find(a => !a.startsWith('-') && /\.html?$/.test(a));
if (!comp) { console.error('usage: node render.mjs comp.html -o out.mp4 [--audio a.wav] [--stills t,t] [--draft] [--ss 2] [--sub 10] [--workers N]'); process.exit(1); }
const out = path.resolve(opt('-o', 'out.mp4'));
const draft = flag('--draft');
const SS = Number(opt('--ss', 1));
const SUB = draft ? 1 : Number(opt('--sub', 10));
const WORKERS = Number(opt('--workers', Math.max(1, Math.min(4, os.cpus().length >> 2))));
const stills = opt('--stills', null)?.split(',').map(Number);
const audio = opt('--audio', null);
const CRF = opt('--crf', '16');
const GRAIN = Number(opt('--grain', 3)); // static luma noise at encode against 8-bit banding of dark gradients; 0 = off

async function loadPlaywright() {
  for (const base of [process.cwd(), path.dirname(path.resolve(comp))]) {
    const req = createRequire(path.join(base, 'noop.js'));
    for (const name of ['playwright', 'playwright-core']) {
      try { return await import(pathToFileURL(req.resolve(name)).href); } catch {}
    }
  }
  // pnpm stores packages under node_modules/.pnpm
  for (let dir = process.cwd(); dir !== path.dirname(dir); dir = path.dirname(dir)) {
    const store = path.join(dir, 'node_modules/.pnpm');
    if (!existsSync(store)) continue;
    const { readdirSync } = await import('node:fs');
    const pkg = readdirSync(store).filter(d => d.startsWith('playwright-core@')).sort().pop();
    if (pkg) return import(pathToFileURL(path.join(store, pkg, 'node_modules/playwright-core/index.mjs')).href);
  }
  console.error('Playwright not found. Run: npm i -D playwright && npx playwright install chromium');
  process.exit(1);
}
const { chromium } = await loadPlaywright();
const CHROME = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium']
  .find(p => existsSync(p));
const browser = await chromium.launch({
  ...(CHROME ? { executablePath: CHROME } : {}), headless: true,
  args: ['--allow-file-access-from-files', '--run-all-compositor-stages-before-draw', '--disable-threaded-animation',
    '--font-render-hinting=none', '--force-color-profile=srgb', '--hide-scrollbars'],
});

async function openComp() {
  const probe = await browser.newPage();
  await probe.goto(pathToFileURL(path.resolve(comp)).href);
  await probe.evaluate(() => window.__ready);
  const meta = await probe.evaluate(() => window.__meta);
  await probe.close();
  const scale = draft ? 0.5 : SS;
  const page = await browser.newPage({ viewport: { width: meta.width, height: meta.height }, deviceScaleFactor: scale });
  page.on('pageerror', e => console.log('pageerror:', e.message));
  await page.goto(pathToFileURL(path.resolve(comp)).href);
  await page.evaluate(() => window.__ready);
  // kill any stray CSS animation/transition: every frame must be a pure function of t
  await page.addStyleTag({ content: '*,*::before,*::after{transition:none!important;animation-play-state:paused!important}' });
  const cdp = await page.context().newCDPSession(page);
  return { page, meta, cdp };
}

// Average sub-frames in LINEAR light: 16-bit RGB, ~sRGB gamma 2.2 → linear, tmix, back.
const LIN = "format=rgb48le,lutrgb=r='65535*pow(val/65535,2.2)':g='65535*pow(val/65535,2.2)':b='65535*pow(val/65535,2.2)'";
const GAM = "lutrgb=r='65535*pow(val/65535,1/2.2)':g='65535*pow(val/65535,1/2.2)':b='65535*pow(val/65535,1/2.2)'";
function blend(subDir, n, file) {
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(n), '-i', path.join(subDir, '%02d.png'),
    '-vf', `${LIN},tmix=frames=${n},select=eq(n\\,${n - 1}),${GAM}`, '-frames:v', '1', file]);
}

// Fast capture: CDP with optimizeForSpeed (Playwright's PNG path is ~5–10× slower on noisy frames).
async function shot(ctx, file) {
  const { data } = await ctx.cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true });
  writeFileSync(file, Buffer.from(data, 'base64'));
}

const seek = (page, t) => page.evaluate(async t => { await window.__seek(t); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }, t);

async function frame(ctx, t, file) {
  const { page, meta } = ctx;
  const fps = meta.fps ?? 30;
  const inBlur = SUB > 1 && (meta.blur ?? []).some(([a, b]) => t >= a && t <= b);
  if (!inBlur) { await seek(page, t); return shot(ctx, file); }
  const cuts = meta.cuts ?? [];
  const subDir = file.replace(/\.png$/, '.sub');
  mkdirSync(subDir, { recursive: true });
  for (let k = 0; k < SUB; k++) {
    let ts = t + ((k + 0.5) / SUB - 0.5) * (0.5 / fps); // 180° shutter, centred on the frame
    for (const c of cuts) { if (t < c && ts >= c) ts = c - 1e-4; if (t >= c && ts < c) ts = c; } // never blend two shots
    await seek(page, ts);
    await shot(ctx, path.join(subDir, `${String(k).padStart(2, '0')}.png`));
  }
  blend(subDir, SUB, file);
  rmSync(subDir, { recursive: true, force: true });
}

const ctx0 = await openComp();
const fps = draft ? 30 : (Number(opt('--fps', 0)) || ctx0.meta.fps || 30);
ctx0.meta.fps = fps;
const { meta } = ctx0;

if (stills) {
  mkdirSync(out, { recursive: true });
  for (const t of stills) await frame(ctx0, t, path.join(out, `still-${t.toFixed(2)}.png`));
  console.log(`stills → ${out}`);
  await browser.close();
  process.exit(0);
}

const N = Math.round(meta.duration * fps);
const dir = out.replace(/\.mp4$/, '') + '.frames';
rmSync(dir, { recursive: true, force: true });
mkdirSync(dir, { recursive: true });
const t0 = Date.now();
const ctxs = [ctx0, ...await Promise.all(Array.from({ length: WORKERS - 1 }, openComp))];
for (const c of ctxs) c.meta.fps = fps;
let next = 0, done = 0;
await Promise.all(ctxs.map(async c => {
  while (next < N) {
    const i = next++;
    await frame(c, i / fps, path.join(dir, `${String(i).padStart(5, '0')}.png`));
    if (++done % 60 === 0) console.log(`frame ${done}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
}));
await browser.close();

// Encode: Lanczos to the target size, limited-range BT.709 with correct tags (setparams makes the
// tags stick), x264 tuned to keep dark gradients and small type intact through platform re-encodes.
const [ow, oh] = draft ? [meta.width >> 1 & ~1, meta.height >> 1 & ~1] : [meta.width, meta.height];
const vf = [`scale=${ow}:${oh}:flags=lanczos+accurate_rnd+full_chroma_int:out_color_matrix=bt709:out_range=tv`,
  'format=yuv420p', ...(GRAIN > 0 ? [`noise=c0s=${GRAIN}:c0f=u`] : []), 'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv'].join(',');
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(dir, '%05d.png'),
  ...(audio ? ['-i', path.resolve(audio)] : []),
  '-vf', vf, '-c:v', 'libx264', '-preset', draft ? 'veryfast' : 'slow', '-crf', draft ? '23' : CRF,
  '-x264-params', `aq-mode=3:keyint=${fps * 2}`, '-maxrate', '25M', '-bufsize', '50M',
  '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv',
  ...(audio ? ['-c:a', 'aac', '-b:a', '256k', '-shortest'] : []), '-movflags', '+faststart', out]);
if (!flag('--keep-frames')) rmSync(dir, { recursive: true, force: true });
console.log(`→ ${out}  (${N} frames, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
