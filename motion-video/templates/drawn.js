/* drawn.js — hand-drawn helpers for motion-video comps (Canvas 2D, no dependencies).
 * Classic script: <script src="drawn.js"></script> → window.Drawn (works under file://, no module CORS).
 * Everything is a pure function of its inputs: pass t (or an exposure-quantised t) and stable seeds.
 *
 *   const D = Drawn.expose(t, [[0, 1.2, 2], [1.2, 1.5, 1], [2.6, 3, 3]]);   // drawings on 2s / 1s / 3s
 *   const pts = Drawn.resample(Drawn.spline(ctrl, true), 3);
 *   Drawn.fillShape(ctx, pts, '#e5402b', { seed: 'hero/body', id: D.id });  // off-register colour
 *   Drawn.inkStroke(ctx, Drawn.boil(pts, { seed: 'hero/body', id: D.id }), { w0: 6, seed: 'hero/body' });
 *   const pace = Drawn.paced(pts);                                          // slows the pen into corners
 *   Drawn.drawOn(ctx, pts, pace(ease(u)), { ink: { w0: 5 }, tip: true });
 *
 * Ported ideas (rewritten, not copied): mg-styles-15 by Vincentwei1021 (MIT) — demos/05-cel-boil
 * (exposure sheet, world-space boil field amp 2.2–2.4 / scale 70, tapered pressure outline, off-register
 * fills) and demos/02-line-art (corner-weighted draw-on, glowing pen tip, dimmed trail);
 * buildwithhanif/claude-animation-skill (MIT) — seeds from a stable NAME, never the frame index;
 * drawings on twos while the camera stays on ones. */
(function (root) {
  'use strict';
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, k) => a + (b - a) * k;
  const sstep = (a, b, x) => { const k = clamp((x - a) / (b - a)); return k * k * (3 - 2 * k); };

  /* ---------------- seeds, PRNG, noise ---------------- */
  /** Stable seed from a name ("ant/body") or a number. Name your drawings; never seed from the frame. */
  function seedOf(s) {
    if (typeof s === 'number') return s >>> 0;
    let h = 2166136261;                                   // FNV-1a
    for (const c of String(s)) h = Math.imul(h ^ c.codePointAt(0), 16777619);
    return h >>> 0;
  }
  /** Integer hash of a lattice point + seed → uint32. */
  function ihash(x, y, s) {
    let h = (s ^ Math.imul(x | 0, 0x27d4eb2d) ^ Math.imul(y | 0, 0x165667b1)) | 0;
    h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d);
    h = Math.imul(h ^ (h >>> 12), 0x297a2d39);
    return (h ^ (h >>> 15)) >>> 0;
  }
  /** Seeded PRNG (mulberry32) → () => [0, 1). */
  function rng(seed) {
    let a = seedOf(seed);
    return () => {
      a = (a + 0x6d2b79f5) | 0;
      let r = Math.imul(a ^ (a >>> 15), 1 | a);
      r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }
  /** 2D gradient (Perlin) noise, seeded, smooth, range ≈ [-1, 1]. No tables: any seed is free. */
  function noise2(x, y, seed = 0) {
    const s = seedOf(seed), ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
    const g = (i, j, dx, dy) => { const a = ihash(ix + i, iy + j, s) * 1.4629180792671596e-9; return Math.cos(a) * dx + Math.sin(a) * dy; };
    const u = fx * fx * fx * (fx * (fx * 6 - 15) + 10), v = fy * fy * fy * (fy * (fy * 6 - 15) + 10);
    return 1.4142 * lerp(lerp(g(0, 0, fx, fy), g(1, 0, fx - 1, fy), u), lerp(g(0, 1, fx, fy - 1), g(1, 1, fx - 1, fy - 1), u), v);
  }

  /* ---------------- exposure sheet ---------------- */
  /** Hold each drawing for N frames. sched: [[t0, t1, frames], …] in seconds, sorted; gaps and the tail
   *  run on `fill` (2s). Returns { t: the time the drawing shows, id: drawing index (counts up across
   *  the film, feed it to boil), step, frame }. Pass D.t to the DRAWING code and raw t to the camera. */
  function expose(t, sched = [], fps = 24, fill = 2) {
    const f = Math.floor(t * fps + 1e-6), spans = [];
    let cur = 0, id = 0;
    for (const [t0, t1, n] of sched) {
      const a = Math.round(t0 * fps), b = Math.round(t1 * fps);
      if (a > cur) spans.push([cur, a, fill]);
      spans.push([a, b, Math.max(1, n | 0)]); cur = b;
    }
    spans.push([cur, Infinity, fill]);
    for (const [a, b, n] of spans) {
      if (f >= b) { id += Math.ceil((b - a) / n); continue; }
      const k = Math.floor((Math.max(f, a) - a) / n);
      return { t: (a + k * n) / fps, id: id + k, step: n, frame: a + k * n };
    }
  }

  /* ---------------- paths ---------------- */
  /** Cumulative arc length of a polyline. */
  function cumlen(P) { const L = [0]; for (let i = 1; i < P.length; i++) L.push(L[i - 1] + Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1])); return L; }
  /** Catmull-Rom through control points → dense polyline (~step px). */
  function spline(P, closed = false, step = 4) {
    const n = P.length; if (n < 3 && !closed) return resample(P, step);
    const at = i => closed ? P[(i % n + n) % n] : P[clamp(i, 0, n - 1)], out = [];
    for (let i = 0; i < (closed ? n : n - 1); i++) {
      const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
      const m = Math.max(1, Math.ceil(Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / step));
      for (let j = 0; j < m; j++) {
        const u = j / m, u2 = u * u, u3 = u2 * u;
        out.push([0, 1].map(d => 0.5 * (2 * p1[d] + (p2[d] - p0[d]) * u + (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * u2 + (3 * p1[d] - p0[d] - 3 * p2[d] + p3[d]) * u3)));
      }
    }
    out.push([...(closed ? P[0] : P[n - 1])]);
    return out;
  }
  /** Even spacing by arc length (boil and the width profile want even points, ~3 px). */
  function resample(P, step = 3) {
    const L = cumlen(P), tot = L[L.length - 1];
    if (!tot) return P.map(p => [p[0], p[1]]);
    const n = Math.max(1, Math.round(tot / step)), out = [];
    for (let i = 0, j = 0; i <= n; i++) {
      const s = tot * i / n;
      while (j < L.length - 2 && L[j + 1] < s) j++;
      const k = (s - L[j]) / ((L[j + 1] - L[j]) || 1);
      out.push([lerp(P[j][0], P[j + 1][0], k), lerp(P[j][1], P[j + 1][1], k)]);
    }
    return out;
  }
  /** The first `frac` (0..1) of a path by arc length, end point interpolated. */
  function prefix(P, frac) {
    const L = cumlen(P), s = clamp(frac) * L[L.length - 1], out = [P[0]];
    for (let i = 1; i < P.length; i++) {
      if (L[i] <= s) { out.push(P[i]); continue; }
      const k = (s - L[i - 1]) / ((L[i] - L[i - 1]) || 1);
      out.push([lerp(P[i - 1][0], P[i][0], k), lerp(P[i - 1][1], P[i][1], k)]); break;
    }
    return out;
  }

  /* ---------------- boil ---------------- */
  /** Line boil: displace points by a world-space noise field re-rolled per DRAWING (not per frame).
   *  drawings: 3–4 variants cycled (3 on held shots); id: Drawn.expose(t).id. Lines that touch boil
   *  together because the field is shared. Boil a moving drawing in its local space, then transform. */
  function boil(P, o = {}) {
    const { seed = 1, amp = 2.3, scale = 70, drawings = 4, id = 0 } = o;
    if (!amp) return P.map(p => [p[0], p[1]]);
    const s = ihash(seedOf(seed), ((id % drawings) + drawings) % drawings, 0x5eed);
    return P.map(([x, y]) => [x + amp * noise2(x / scale, y / scale, s), y + amp * noise2(x / scale + 41.3, y / scale - 17.9, s)]);
  }

  /* ---------------- ink ---------------- */
  /** Variable-width outline polygon (round caps) around a dense polyline; half(i) = half-width at point i. */
  function outline(P, half) {
    const n = P.length, Lp = [], Rp = [], ang = (p, q) => Math.atan2(q[1] - p[1], q[0] - p[0]);
    for (let i = 0; i < n; i++) {
      const a = P[Math.max(0, i - 1)], b = P[Math.min(n - 1, i + 1)];
      let tx = b[0] - a[0], ty = b[1] - a[1]; const l = Math.hypot(tx, ty) || 1; tx /= l; ty /= l;
      const w = half(i);
      Lp.push([P[i][0] - ty * w, P[i][1] + tx * w]); Rp.push([P[i][0] + ty * w, P[i][1] - tx * w]);
    }
    const cap = (c, a0, w, out) => { if (w >= 0.6) for (let k = 1; k < 8; k++) { const a = a0 - Math.PI * k / 8; out.push([c[0] + Math.cos(a) * w, c[1] + Math.sin(a) * w]); } };
    const poly = [...Lp];
    cap(P[n - 1], ang(P[n - 2], P[n - 1]) + Math.PI / 2, half(n - 1), poly);
    for (let i = n - 1; i >= 0; i--) poly.push(Rp[i]);
    cap(P[0], ang(P[0], P[1]) - Math.PI / 2, half(0), poly);
    return poly;
  }
  const fillPoly = (ctx, poly, color) => { ctx.beginPath(); poly.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath(); ctx.fillStyle = color; ctx.fill(); };
  /** Tapered brush stroke. w0→w1 px along the line; taper = px of thinning at [start, end] (a number for
   *  both, 0 = blunt); jit = pressure wobble (±35 %); min = width left at the very tip. Returns the polygon. */
  function inkStroke(ctx, P, o = {}) {
    const { w0 = 6, w1 = w0, taper = [14, 26], min = 0.25, jit = 0.35, seed = 1, color = '#1c1613', dense = false } = o;
    const pts = dense ? P : resample(P, 3);
    if (pts.length < 2) return [];
    const L = cumlen(pts), tot = L[L.length - 1] || 1, sd = seedOf(seed);
    const [ta, tb] = Array.isArray(taper) ? taper : [taper, taper];
    const poly = outline(pts, i => {
      const s = L[i];
      let w = lerp(w0, w1, s / tot) * (1 + jit * noise2(s / 60, 3.1, sd));
      w *= min + (1 - min) * Math.min(ta ? sstep(0, ta, s) : 1, tb ? sstep(0, tb, tot - s) : 1);
      return Math.max(0, w) / 2;
    });
    fillPoly(ctx, poly, color);
    return poly;
  }
  /** Flat colour under the ink, boiled on its own seed and printed off-register (hand colouring). */
  function fillShape(ctx, P, color, o = {}) {
    const { dx = -5, dy = 4, seed = 1 } = o;
    const pts = boil(P, { ...o, seed: seedOf(seed) ^ 0x9e3779b9 }).map(([x, y]) => [x + dx, y + dy]);
    fillPoly(ctx, pts, color);
    return pts;
  }

  /* ---------------- draw-on ---------------- */
  /** Pen-tip glow: a wide halo, a 15 px glow and a hot ~3 px core (line-art nib). */
  function glow(ctx, [x, y], o = {}) {
    const { r = 15, core = 3, color = '255,246,220', a = 1 } = o;
    for (const [R, al] of [[r * 3.7, 0.09], [r, 0.34], [core, 0.95]]) {
      const g = ctx.createRadialGradient(x, y, 0, x, y, R);
      g.addColorStop(0, `rgba(${color},${al * a})`); g.addColorStop(1, `rgba(${color},0)`);
      ctx.fillStyle = g; ctx.fillRect(x - R, y - R, 2 * R, 2 * R);
    }
  }
  const hex = c => [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));
  /** Draw the first `progress` (arc-length fraction) of a path. Options:
   *  ink: {…inkStroke opts} for a tapered brush (the head stays full width while drawing), else a plain
   *  round-capped line of `w` px in `color`; trail: { color, len } blends older line toward `color`
   *  over `len` px behind the head (line art dims old segments to ~35 %); tip: true | glow opts.
   *  Returns the head point (aim the camera a little ahead of it). */
  function drawOn(ctx, P, progress, o = {}) {
    const { ink = null, w = 3, color = '#e9d7a5', trail = null, tip = false } = o;
    if (progress <= 0 || P.length < 2) return null;
    const part = prefix(P, progress), head = part[part.length - 1], done = progress >= 1;
    if (ink) {
      const tp = ink.taper ?? [14, 26], [ta, tb] = Array.isArray(tp) ? tp : [tp, tp];
      inkStroke(ctx, part, { color, ...ink, taper: [ta, done ? tb : 0] });
    } else {
      ctx.save(); ctx.lineCap = ctx.lineJoin = 'round'; ctx.lineWidth = w;
      if (!trail) { ctx.strokeStyle = color; ctx.beginPath(); part.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.stroke(); }
      else {                                   // opaque colour blend per chunk: overlaps stay invisible
        const L = cumlen(part), tot = L[L.length - 1], A = hex(color), B = hex(trail.color);
        for (let i0 = 0; i0 < part.length - 1; i0 += 8) {
          const i1 = Math.min(part.length - 1, i0 + 8), k = sstep(0, trail.len ?? 600, tot - L[(i0 + i1) >> 1]);
          ctx.strokeStyle = `rgb(${A.map((v, j) => Math.round(lerp(v, B[j], k))).join(',')})`;
          ctx.beginPath(); for (let i = i0; i <= i1; i++) i === i0 ? ctx.moveTo(...part[i]) : ctx.lineTo(...part[i]); ctx.stroke();
        }
      }
      ctx.restore();
    }
    if (tip && !done) glow(ctx, head, tip === true ? {} : tip);
    return head;
  }
  /** Corner-weighted pacing: returns u (0..1 of the stroke's time, eased) → arc-length fraction, so the
   *  pen slows into corners (line art: time ∝ length × (1 + k·min(curvature, cap)), curvature in rad/px
   *  smoothed over `sigma` px). Build once per path; pass the same resampled points to drawOn. */
  function paced(P, o = {}) {
    const { k = 9, cap = 0.3, sigma = 7 } = o, n = P.length, L = cumlen(P), tot = L[n - 1] || 1;
    const turn = new Float64Array(n), tau = new Float64Array(n);
    for (let i = 1; i < n - 1; i++) {
      const d = Math.atan2(P[i + 1][1] - P[i][1], P[i + 1][0] - P[i][0]) - Math.atan2(P[i][1] - P[i - 1][1], P[i][0] - P[i - 1][0]);
      turn[i] = Math.abs(Math.atan2(Math.sin(d), Math.cos(d)));
    }
    const step = tot / Math.max(1, n - 1), sg = Math.max(1e-3, sigma / step), R = Math.ceil(sg * 3);
    for (let i = 1; i < n; i++) {
      let acc = 0, ws = 0;
      for (let j = Math.max(0, i - R); j <= Math.min(n - 1, i + R); j++) { const g = Math.exp(-((j - i) ** 2) / (2 * sg * sg)); acc += turn[j] * g; ws += g; }
      tau[i] = tau[i - 1] + (L[i] - L[i - 1]) * (1 + k * Math.min(acc / ws / step, cap));
    }
    return u => {
      const x = clamp(u) * tau[n - 1]; let lo = 0, hi = n - 1;
      while (hi - lo > 1) { const m = (lo + hi) >> 1; if (tau[m] <= x) lo = m; else hi = m; }
      return lerp(L[lo], L[hi], (x - tau[lo]) / ((tau[hi] - tau[lo]) || 1)) / tot;
    };
  }

  root.Drawn = { seedOf, rng, noise2, expose, cumlen, spline, resample, prefix, boil, outline, inkStroke, fillShape, glow, drawOn, paced };
})(typeof window !== 'undefined' ? window : globalThis);
