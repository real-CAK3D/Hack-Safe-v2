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

  /* ------------------------------------------------------------- GPS/Sensors radar (Signals tab)
     Sweep angle is computed once per frame from wall-clock time, so "lit exactly while the sweep
     passes, fades after" falls out of the math instead of being hand-tuned CSS animation-delay
     guesswork (which never actually lined up with the sweep line). */
  const GPS_PERIOD = 6; // seconds per revolution, matches the look of the old CSS sweep
  function drawGpsRadar(cv, dt) {
    const rect = cv.getBoundingClientRect();
    const w = Math.round(rect.width), h = Math.round(rect.height);
    if (w < 10 || h < 10) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    const c = cv.getContext('2d');
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const data = cv.__gpsData || { count: 0, sats: [], fixed: false };
    const cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - 3;
    const col = resolveColor(data.fixed ? 'var(--green)' : 'var(--yellow)', cv);

    // stable synthetic layout: same golden-angle spiral the old CSS version used, so satellites
    // don't jump around the dial as the count changes tick to tick
    const n = Math.max(0, Math.min(24, data.count | 0));
    const blips = cv.__gpsBlips || (cv.__gpsBlips = []);
    while (blips.length < n) {
      const i = blips.length, a = (i * 137.508) % 360, r = (0.28 + (i * 17 % 27) / 100);
      blips.push({ a: a * Math.PI / 180, r, lit: 0 });
    }
    blips.length = n;

    const now = performance.now() / 1000;
    const sweep = (now % GPS_PERIOD) / GPS_PERIOD * TAU - Math.PI / 2; // start pointing up, like the old CSS version

    // rings
    c.strokeStyle = 'rgba(255,255,255,.08)'; c.lineWidth = 1;
    for (let ring = 1; ring <= 3; ring++) { c.beginPath(); c.arc(cx, cy, R * ring / 3, 0, TAU); c.stroke(); }

    // sweep line + soft trailing wedge
    const grad = c.createConicGradient ? c.createConicGradient(sweep - 1.15, cx, cy) : null;
    if (grad) {
      grad.addColorStop(0, col + '00'); grad.addColorStop(1, col + '3d');
      c.beginPath(); c.moveTo(cx, cy); c.arc(cx, cy, R, sweep - 1.15, sweep); c.closePath();
      c.fillStyle = grad; c.fill();
    }
    c.beginPath(); c.moveTo(cx, cy); c.lineTo(cx + Math.cos(sweep) * R, cy + Math.sin(sweep) * R);
    c.strokeStyle = col; c.lineWidth = 1.6; c.shadowColor = col; c.shadowBlur = 8; c.stroke(); c.shadowBlur = 0;

    // blips: brighten the instant the sweep crosses them, then decay
    blips.forEach(b => {
      let diff = (sweep - b.a) % TAU; if (diff < 0) diff += TAU;
      if (diff < 0.12) b.lit = 1; else b.lit = Math.max(0, b.lit - dt * 0.55);
      const x = cx + Math.cos(b.a) * b.r * R, y = cy + Math.sin(b.a) * b.r * R;
      const rad = 2.2 + b.lit * 2.2;
      if (b.lit > 0.04) { c.beginPath(); c.arc(x, y, rad + 5 * b.lit, 0, TAU); c.fillStyle = col + Math.round(b.lit * 50).toString(16).padStart(2, '0'); c.fill(); }
      c.beginPath(); c.arc(x, y, rad, 0, TAU); c.fillStyle = col; c.globalAlpha = 0.25 + b.lit * 0.75; c.fill(); c.globalAlpha = 1;
    });
  }

  /* ------------------------------------------------------------- Weather Ops radar (Signals tab)
     OpenWeatherMap's free tile API only ever gives one CURRENT-moment tile -- there's no real
     historical or forecast radar frame to fetch. Rather than fake that, this draws a stylized
     precip-cell field that drifts along the live wind vector, and lets Recent/Now/Upcoming just
     shift the time offset those cells are drawn at (extrapolation, not real recorded radar). */
  const REFLECT_STOPS = [[0, '#1a7a34'], [0.4, '#27c93f'], [0.65, '#ffbd2e'], [0.85, '#ff8c2e'], [1, '#ff5f56']];
  function reflectivityColor(t) {
    t = Math.min(1, Math.max(0, t));
    for (let i = 1; i < REFLECT_STOPS.length; i++) {
      if (t <= REFLECT_STOPS[i][0]) {
        const [t0, c0] = REFLECT_STOPS[i - 1], [t1, c1] = REFLECT_STOPS[i];
        return t1 > t0 ? (((t - t0) / (t1 - t0)) < 0.5 ? c0 : c1) : c1;
      }
    }
    return REFLECT_STOPS[REFLECT_STOPS.length - 1][1];
  }
  const WX_FILTER_MIN = { recent: -40, now: 0, upcoming: 40 };
  function drawWeatherRadar(cv, dt) {
    const rect = cv.getBoundingClientRect();
    const w = Math.round(rect.width), h = Math.round(rect.height);
    if (w < 10 || h < 10) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    const c = cv.getContext('2d');
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const data = cv.__wxData || { cls: 'idle', windMph: 0, windDir: 0, precipMm: 0, rf: 'now' };
    const cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - 3;

    // stable synthetic cell field: golden-angle spiral like the GPS radar, so cells don't
    // reshuffle every render -- only their drift position changes.
    const baseIntensity = { storm: 0.92, rain: 0.62, snow: 0.5, cloud: 0.22, clear: 0.05, idle: 0.08 }[data.cls] ?? 0.15;
    const count = { storm: 13, rain: 10, snow: 9, cloud: 6, clear: 2, idle: 3 }[data.cls] ?? 4;
    const cells = cv.__wxCells || (cv.__wxCells = []);
    while (cells.length < count) {
      const i = cells.length, a = (i * 137.508) % 360, r = 0.15 + (i * 23 % 70) / 100;
      cells.push({ bx: Math.cos(a * Math.PI / 180) * r, by: Math.sin(a * Math.PI / 180) * r, size: 0.14 + (i * 11 % 20) / 100, jitter: (i * 53 % 100) / 100 });
    }
    cells.length = count;

    // wind: meteorological windDir is where wind blows FROM, so travel direction is +180deg.
    const travelRad = ((data.windDir || 0) + 180) * Math.PI / 180;
    const speed = Math.min(1, (data.windMph || 0) / 45);
    const now = performance.now() / 1000;
    const ambientDrift = now * (0.015 + speed * 0.05); // slow ambient motion even at zero wind
    const filterShift = (WX_FILTER_MIN[data.rf] ?? 0) / 90 * (0.25 + speed * 0.35);
    const shift = ambientDrift + filterShift;
    const tx = Math.cos(travelRad), ty = Math.sin(travelRad);

    // clip to the radar dome
    c.save();
    c.beginPath(); c.arc(cx, cy, R, 0, TAU); c.clip();
    c.fillStyle = 'rgba(4,10,8,.18)'; c.fillRect(0, 0, w, h);

    cells.forEach(cell => {
      // drift each cell along the wind vector in a square field, wrapping into [-1.1, 1.1] so
      // it scrolls continuously; the dome clip above hides anything currently outside the circle.
      const wob = Math.sin(now * 0.3 + cell.bx * 9 + cell.by * 5) * 0.05;
      let ux = cell.bx + tx * shift * (0.7 + cell.jitter * 0.6);
      let uy = cell.by + ty * shift * (0.7 + cell.jitter * 0.6) + wob;
      ux = (((ux + 1.1) % 2.2) + 2.2) % 2.2 - 1.1;
      uy = (((uy + 1.1) % 2.2) + 2.2) % 2.2 - 1.1;
      const px = cx + ux * R, py = cy + uy * R;
      const intensity = Math.min(1, baseIntensity + Math.sin(now * 0.4 + cell.jitter * 6) * 0.08 + (data.precipMm || 0) / 20);
      const col = reflectivityColor(intensity);
      const rad = R * (cell.size + intensity * 0.05);
      const grad = c.createRadialGradient(px, py, 0, px, py, rad);
      grad.addColorStop(0, col + 'cc'); grad.addColorStop(0.6, col + '55'); grad.addColorStop(1, col + '00');
      c.beginPath(); c.arc(px, py, rad, 0, TAU); c.fillStyle = grad; c.fill();
    });

    // range rings + compass ticks
    c.strokeStyle = 'rgba(255,255,255,.1)'; c.lineWidth = 1;
    for (let ring = 1; ring <= 3; ring++) { c.beginPath(); c.arc(cx, cy, R * ring / 3, 0, TAU); c.stroke(); }
    c.beginPath(); c.moveTo(cx - R, cy); c.lineTo(cx + R, cy); c.moveTo(cx, cy - R); c.lineTo(cx, cy + R); c.stroke();
    c.restore();

    // station marker + wind arrow
    c.beginPath(); c.arc(cx, cy, 2.5, 0, TAU); c.fillStyle = '#5ac8fa'; c.shadowColor = '#5ac8fa'; c.shadowBlur = 6; c.fill(); c.shadowBlur = 0;
    if ((data.windMph || 0) > 1) {
      const ax = cx + Math.cos(travelRad) * R * 0.22, ay = cy + Math.sin(travelRad) * R * 0.22;
      c.strokeStyle = '#dbeafe99'; c.lineWidth = 1.4;
      c.beginPath(); c.moveTo(cx, cy); c.lineTo(ax, ay); c.stroke();
      c.beginPath(); c.moveTo(ax, ay);
      c.lineTo(ax - Math.cos(travelRad - 0.4) * 5, ay - Math.sin(travelRad - 0.4) * 5);
      c.lineTo(ax - Math.cos(travelRad + 0.4) * 5, ay - Math.sin(travelRad + 0.4) * 5);
      c.closePath(); c.fillStyle = '#dbeafe99'; c.fill();
    }
    c.font = '8px monospace'; c.fillStyle = 'rgba(255,255,255,.35)'; c.textAlign = 'center';
    c.fillText('N', cx, cy - R - 3); c.fillText('S', cx, cy + R + 9);
    c.textAlign = 'left'; c.fillText('E', cx + R + 3, cy + 3);
    c.textAlign = 'right'; c.fillText('W', cx - R - 3, cy + 3);
  }

  let raf = 0, lastGps = 0, lastWx = 0;
  function loop(ts) {
    raf = 0;
    if (!document.hidden) {
      const reg = window.__waveRegistry;
      if (reg && reg.size) {
        document.querySelectorAll('canvas.tc-canvas').forEach(cv => {
          const entry = reg.get(cv.id);
          if (entry) draw(cv, entry);
        });
      }
      const gps = document.querySelector('canvas.gps-radar-canvas');
      if (gps) { const dt = lastGps ? Math.min((ts - lastGps) / 1000, .1) : 0.016; lastGps = ts; drawGpsRadar(gps, dt); }
      else lastGps = 0;
      const wx = document.querySelector('canvas.weather-radar-canvas');
      if (wx) { const dt = lastWx ? Math.min((ts - lastWx) / 1000, .1) : 0.016; lastWx = ts; drawWeatherRadar(wx, dt); }
      else lastWx = 0;
    } else { lastGps = 0; lastWx = 0; }
    raf = requestAnimationFrame(loop);
  }
  raf = requestAnimationFrame(loop);
})();
