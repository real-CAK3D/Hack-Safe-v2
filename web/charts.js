/* Spac3-Gh0st inline telemetry charts: renders every canvas produced by app.js's liveWave()
   (Systems + Signals tabs) in the same visual language as the Deck tab's telemetry chart --
   gradient-filled smoothed line, hover crosshair + tooltip. app.js owns the data (it just pushes
   numbers into window.__waveRegistry keyed by canvas id); this file only draws.
   One shared rAF loop redraws every visible .tc-canvas each frame; hidden-tab canvases
   (display:none ancestor => 0 size) are skipped cheaply via getBoundingClientRect. */
(function () {
  'use strict';
  const TAU = Math.PI * 2;
  const REDUCED = (() => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; } })();
  const hover = { id: null, x: null };

  function resolveColor(spec, el) {
    if (typeof spec === 'string' && spec.startsWith('var(')) {
      const name = spec.slice(4, -1).trim();
      const v = getComputedStyle(el).getPropertyValue(name).trim();
      if (v) return v;
    }
    return spec || '#27c93f';
  }

  function smoothPath(c, pts) {
    c.beginPath();
    if (!pts.length) return;
    c.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length - 1; i++) {
      const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2;
      c.quadraticCurveTo(pts[i][0], pts[i][1], mx, my);
    }
    if (pts.length > 1) c.lineTo(pts[pts.length - 1][0], pts[pts.length - 1][1]);
  }

  function draw(cv, entry) {
    const rect = cv.getBoundingClientRect();
    const w = Math.round(rect.width), h = Math.round(rect.height);
    if (w < 6 || h < 6) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    const c = cv.getContext('2d');
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const nums = entry.values && entry.values.length ? entry.values : [0];
    const lo = entry.lo, hi = Math.max(entry.hi, Math.max.apply(null, nums) + 1e-6);
    const pad = 2;
    const X = i => pad + (nums.length > 1 ? i / (nums.length - 1) : 0) * (w - pad * 2);
    const Y = v => h - pad - (Math.min(Math.max(v, lo), hi) - lo) / ((hi - lo) || 1) * (h - pad * 2);
    const col = resolveColor(entry.color, cv);
    const pts = nums.map((v, i) => [X(i), Y(v)]);

    // grid: a couple of faint horizontal guides, matching the Deck chart's grid language
    c.strokeStyle = 'rgba(255,255,255,.06)'; c.lineWidth = 1;
    c.beginPath(); c.moveTo(0, h / 2); c.lineTo(w, h / 2); c.stroke();

    smoothPath(c, pts);
    const g = c.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, col + '4d'); g.addColorStop(1, col + '00');
    c.lineTo(pts[pts.length - 1][0], h - pad); c.lineTo(pts[0][0], h - pad); c.closePath();
    c.fillStyle = g; c.fill();

    smoothPath(c, pts);
    c.strokeStyle = col; c.lineWidth = 1.5; c.lineJoin = 'round'; c.lineCap = 'round';
    c.shadowColor = col; c.shadowBlur = 4; c.stroke(); c.shadowBlur = 0;

    const last = pts[pts.length - 1];
    c.beginPath(); c.arc(last[0], last[1], 2, 0, TAU); c.fillStyle = col; c.fill();

    const tip = cv.__tip || (cv.__tip = document.querySelector(`.tc-tip[data-for="${cv.id}"]`));
    if (hover.id === cv.id && hover.x != null && !REDUCED) {
      const hx = Math.min(Math.max(hover.x, 0), w);
      let idx = nums.length > 1 ? Math.round((hx - pad) / (w - pad * 2) * (nums.length - 1)) : 0;
      idx = Math.min(nums.length - 1, Math.max(0, idx));
      const v = nums[idx], px = X(idx), py = Y(v);
      c.strokeStyle = 'rgba(255,255,255,.35)'; c.setLineDash([2, 2]);
      c.beginPath(); c.moveTo(px, 0); c.lineTo(px, h); c.stroke(); c.setLineDash([]);
      c.beginPath(); c.arc(px, py, 3, 0, TAU); c.fillStyle = col; c.fill(); c.strokeStyle = '#000'; c.lineWidth = 1; c.stroke();
      if (tip) {
        tip.hidden = false;
        tip.textContent = (Math.round(v * 10) / 10).toString();
        tip.style.left = Math.min(Math.max(px - 16, 0), w - 34) + 'px';
      }
    } else if (tip) tip.hidden = true;
  }

  function pointFromEvent(e, cv) {
    const r = cv.getBoundingClientRect();
    return e.clientX - r.left;
  }
  document.addEventListener('pointermove', e => {
    const cv = e.target && e.target.closest && e.target.closest('canvas.tc-canvas');
    if (cv) { hover.id = cv.id; hover.x = pointFromEvent(e, cv); }
    else if (hover.id) { hover.id = null; hover.x = null; }
  });
  document.addEventListener('pointerdown', e => {
    const cv = e.target && e.target.closest && e.target.closest('canvas.tc-canvas');
    if (cv) { hover.id = cv.id; hover.x = pointFromEvent(e, cv); }
  });

  let raf = 0;
  function loop() {
    raf = 0;
    if (!document.hidden) {
      const reg = window.__waveRegistry;
      if (reg && reg.size) {
        document.querySelectorAll('canvas.tc-canvas').forEach(cv => {
          const entry = reg.get(cv.id);
          if (entry) draw(cv, entry);
        });
      }
    }
    raf = requestAnimationFrame(loop);
  }
  raf = requestAnimationFrame(loop);
})();
