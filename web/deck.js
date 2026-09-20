/* Spac3-Gh0st "Deck": the live-visuals tab.
   Radial gauges, a scrolling telemetry chart with hover crosshair, a sweeping signal radar,
   a Wi-Fi channel spectrum analyzer, a draggable network graph, sortable device / process tables,
   disk rings and an event timeline. Everything reads what the dashboard already collects
   (lastStatus + /api/metrics), and the animation loop only runs while the Deck tab is open. */
(function () {
  'use strict';

  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const store = { get: (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
  const status = () => { try { return typeof lastStatus !== 'undefined' ? lastStatus : null; } catch (e) { return null; } };
  const css = n => getComputedStyle(document.body).getPropertyValue(n).trim() || '#27c93f';
  const TAU = Math.PI * 2;
  const hash = str => { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967296; };
  const num = v => { if (v === null || v === undefined || v === '') return null; v = parseFloat(v); return isFinite(v) ? v : null; };
  const fmtRate = b => { b = b || 0; return b > 1048576 ? (b / 1048576).toFixed(1) + ' MB/s' : b > 1024 ? (b / 1024).toFixed(0) + ' KB/s' : Math.round(b) + ' B/s'; };

  let demo = store.get('deckDemo', '0') === '1' || /[?&]demo=1\b/.test(location.search);
  let root = null, built = false;
  const state = { samples: [], lastT: 0, range: 300, hidden: {}, filter: 'all', search: '', sort: { k: 'sig', dir: -1 }, psort: 'cpu', selected: null, evFilter: 'all' };

  /* ------------------------------------------------------------------ demo data (clearly labelled in the UI) */
  function demoData() {
    const R = (id, a, b) => a + hash(id) * (b - a);
    const wifi = ['HomeNet-5G', 'Space-Brigade', 'NukeBox', 'ORBI79', 'xfinitywifi', 'Ring-Setup', 'Guest-Lab', 'CoffeeShop', 'TP-Link_8A2C'].map((s, i) => ({ ssid: s, channel: String([1, 6, 11, 6, 1, 11, 3, 9, 36][i]), signal: String(Math.round(R(s, 28, 96))), security: i % 4 === 3 ? 'OPEN' : 'WPA2', connected: i === 0 }));
    const bt = ['Pixel Buds', 'Living Room TV', 'K-270W Keyboard', 'Smart Lock', 'JBL Flip'].map((n, i) => ({ mac: 'AA:BB:CC:00:00:0' + i, name: n, connected: i < 2 }));
    const lan = ['router', 'nas', 'pi-hole', 'printer', 'thermostat', 'phone', 'laptop'].map((n, i) => ({ ip: '192.168.1.' + (i === 0 ? 1 : 10 + i * 7), mac: 'DC:A6:32:00:00:0' + i, vendor: ['Netgear', 'Synology', 'Raspberry Pi', 'HP', 'Nest', 'Apple', 'Intel'][i], hostname: n, state: 'REACHABLE' }));
    return { wifi, bt, lan };
  }
  function devices() {
    const s = status() || {};
    let wifi = (s.wifi && s.wifi.networks) || [], bt = (s.bluetooth && s.bluetooth.devices) || [], lan = (s.lan && s.lan.devices) || [];
    let isDemo = false;
    if (demo) { const d = demoData(); if (!wifi.length) { wifi = d.wifi; isDemo = true; } if (!bt.length) { bt = d.bt; isDemo = true; } if (!lan.length) { lan = d.lan; isDemo = true; } }
    const out = [];
    wifi.forEach(n => out.push({ id: 'w:' + n.ssid, type: 'wifi', name: n.ssid || '<hidden>', sub: 'ch ' + (n.channel || '?') + ' · ' + (n.security || 'n/a'), sig: num(n.signal) || 0, ch: num(n.channel), sec: n.security || '', on: !!n.connected }));
    bt.forEach(d => out.push({ id: 'b:' + d.mac, type: 'bt', name: d.name || 'Unknown', sub: d.mac, sig: Math.round(35 + hash(d.mac) * 50), on: !!d.connected }));
    lan.forEach(d => out.push({ id: 'l:' + d.ip, type: 'lan', name: d.hostname || d.ip, sub: d.ip + (d.vendor && d.vendor !== 'Unknown' ? ' · ' + d.vendor : ''), sig: Math.round(45 + hash(d.ip) * 50), on: true }));
    return { list: out, isDemo };
  }

  /* ------------------------------------------------------------------ DOM scaffold */
  const CARD = (cls, title, body, extra) => `<section class="card deck-card ${cls}"><h2>${title}${extra || ''}</h2>${body}</section>`;
  function build() {
    root = $('#tab-deck'); if (!root || built) return; built = true;
    root.innerHTML = `
      <section class="card page-hero deck-hero"><h2>Deck</h2><p class="mini">Live telemetry, radar and network visuals. <span class="deck-demo-badge" id="deckDemoBadge" hidden>DEMO DATA on empty panels</span></p>
        <div class="deck-actions"><button id="deckDemoBtn" type="button">Demo data: <b>off</b></button><button id="deckPauseBtn" type="button">Pause</button></div></section>
      <section class="deck-gauges" id="deckGauges"></section>
      ${CARD('deck-chart', 'System Telemetry', `<div class="deck-toolbar"><div class="seg" id="deckRange"><button data-r="60">1m</button><button data-r="300" class="on">5m</button><button data-r="900">15m</button><button data-r="1800">30m</button></div><div class="deck-legend" id="deckLegend"></div></div><div class="deck-canvas-wrap"><canvas id="deckChart"></canvas><div class="deck-tip" id="deckChartTip" hidden></div></div><div class="deck-stats" id="deckStats"></div>`)}
      ${CARD('deck-radar', 'Signal Radar', `<div class="deck-canvas-wrap sq"><canvas id="deckRadar"></canvas><div class="deck-tip" id="deckRadarTip" hidden></div></div><div class="deck-legend static"><i class="lg wifi"></i>Wi-Fi<i class="lg bt"></i>Bluetooth<i class="lg lan"></i>LAN</div>`)}
      ${CARD('deck-spectrum', 'Wi-Fi Spectrum', `<div class="deck-canvas-wrap"><canvas id="deckSpectrum"></canvas></div><div class="mini" id="deckSpectrumNote"></div>`)}
      ${CARD('deck-graph', 'Network Graph', `<div class="deck-canvas-wrap"><canvas id="deckGraph"></canvas><div class="deck-tip" id="deckGraphTip" hidden></div></div><div class="mini">Drag nodes. Solid links are connected, dashed are visible-only.</div>`)}
      ${CARD('deck-devices', 'Devices', `<div class="deck-toolbar"><div class="seg" id="deckFilter"><button data-f="all" class="on">All</button><button data-f="wifi">Wi-Fi</button><button data-f="bt">Bluetooth</button><button data-f="lan">LAN</button></div><input id="deckSearch" type="search" placeholder="Filter..." aria-label="Filter devices"></div><div class="deck-table-wrap"><table class="deck-table" id="deckDevTable"></table></div>`)}
      ${CARD('deck-procs', 'Top Processes', `<div class="deck-toolbar"><div class="seg" id="deckPsort"><button data-p="cpu" class="on">CPU</button><button data-p="mem">Memory</button></div></div><div class="deck-table-wrap"><table class="deck-table" id="deckProcTable"></table></div>`)}
      ${CARD('deck-disks', 'Storage', `<div class="deck-rings" id="deckRings"></div>`)}
      ${CARD('deck-events', 'Event Timeline', `<div class="deck-toolbar"><div class="seg" id="deckEvFilter"><button data-e="all" class="on">All</button><button data-e="alert">Alerts</button><button data-e="service">Services</button><button data-e="chatter">Chatter</button></div></div><ol class="deck-timeline" id="deckTimeline"></ol>`)}
      ${CARD('deck-pulse', 'System Pulse', `<div class="deck-canvas-wrap short"><canvas id="deckPulse"></canvas></div><div class="deck-posture" id="deckPosture"></div>`)}`;
    wire();
  }

  function wire() {
    $('#deckDemoBtn').onclick = () => { demo = !demo; store.set('deckDemo', demo ? '1' : '0'); refreshAll(true); };
    $('#deckPauseBtn').onclick = e => { paused = !paused; e.target.textContent = paused ? 'Resume' : 'Pause'; };
    const seg = (id, key, cb) => $(id).addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; $$('button', $(id)).forEach(x => x.classList.toggle('on', x === b)); cb(b.dataset[key]); });
    seg('#deckRange', 'r', v => { state.range = +v; });
    seg('#deckFilter', 'f', v => { state.filter = v; renderDevices(); });
    seg('#deckPsort', 'p', v => { state.psort = v; renderProcs(); });
    seg('#deckEvFilter', 'e', v => { state.evFilter = v; renderEvents(); });
    $('#deckSearch').addEventListener('input', e => { state.search = e.target.value.toLowerCase(); renderDevices(); });
    $('#deckDevTable').addEventListener('click', e => {
      const th = e.target.closest('th[data-k]'); if (th) { const k = th.dataset.k; state.sort = { k, dir: state.sort.k === k ? -state.sort.dir : (k === 'name' ? 1 : -1) }; renderDevices(); return; }
      const tr = e.target.closest('tr[data-id]'); if (tr) { state.selected = state.selected === tr.dataset.id ? null : tr.dataset.id; renderDevices(); }
    });
  }

  /* ------------------------------------------------------------------ gauges (SVG, CSS-transitioned) */
  const GAUGES = [
    { k: 'cpu', label: 'CPU', unit: '%', get: s => num(s.system && s.system.cpu_live && s.system.cpu_live.percent), warn: 70, bad: 90, sub: s => { const c = s.system && s.system.cpu_live; return c ? ((c.cores || '?') + ' cores' + (c.freq_mhz ? ' · ' + Math.round(c.freq_mhz) + ' MHz' : '')) : ''; } },
    { k: 'mem', label: 'Memory', unit: '%', get: s => num(s.system && s.system.memory && s.system.memory.percent), warn: 75, bad: 90, sub: s => { const m = s.system && s.system.memory; return m && m.total_mb ? m.used_mb + ' / ' + m.total_mb + ' MB' : ''; } },
    { k: 'disk', label: 'Disk', unit: '%', get: s => { const d = s.system && s.system.disk_all && s.system.disk_all[0]; const m = d && /(\d+)%/.exec(d.use_percent || ''); return m ? +m[1] : null; }, warn: 80, bad: 93, sub: s => { const d = s.system && s.system.disk_all && s.system.disk_all[0]; return d ? d.mount + ' · ' + d.avail + ' free' : ''; } },
    { k: 'temp', label: 'CPU Temp', unit: '°C', max: 90, get: s => num(s.system && s.system.cpu_temp_c), warn: 65, bad: 75, sub: s => { const f = s.system && s.system.cpu_temp_f; return f != null ? f + ' °F' : 'sensor unavailable'; } }
  ];
  const R = 54, C = 2 * Math.PI * R, ARC = 0.75; // 270-degree gauge
  function buildGauges() {
    $('#deckGauges').innerHTML = GAUGES.map(g => `
      <div class="card deck-gauge" data-k="${g.k}" data-state="na">
        <svg viewBox="0 0 140 140" aria-hidden="true">
          <defs><linearGradient id="gg-${g.k}" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="var(--gc, var(--green))"/><stop offset="1" stop-color="var(--gc2, var(--cyan))"/></linearGradient></defs>
          <g transform="rotate(135 70 70)">
            <circle class="track" cx="70" cy="70" r="${R}" stroke-dasharray="${C * ARC} ${C}"/>
            <circle class="ticks" cx="70" cy="70" r="${R + 9}" stroke-dasharray="1.2 ${((2 * Math.PI * (R + 9)) * ARC / 27) - 1.2}"/>
            <circle class="arc" cx="70" cy="70" r="${R}" stroke="url(#gg-${g.k})" stroke-dasharray="0 ${C}"/>
          </g>
          <g class="needle-g"><line class="needle" x1="70" y1="70" x2="70" y2="24"/><circle cx="70" cy="70" r="4.5" class="hub"/></g>
        </svg>
        <div class="gv"><b>--</b><small>${g.unit}</small></div><div class="gl">${g.label}</div><div class="gs"></div>
      </div>`).join('');
  }
  function renderGauges() {
    const s = status(); if (!s) return;
    GAUGES.forEach(g => {
      const el = $(`.deck-gauge[data-k="${g.k}"]`); if (!el) return;
      const v = g.get(s); const max = g.max || 100;
      const st = v == null ? 'na' : (g.bad != null && v >= g.bad ? 'bad' : g.warn != null && v >= g.warn ? 'warn' : 'ok');
      el.dataset.state = st;
      const f = v == null ? 0 : clamp(v / max, 0, 1);
      $('.arc', el).setAttribute('stroke-dasharray', `${C * ARC * f} ${C}`);
      $('.needle-g', el).style.transform = `rotate(${-135 + f * 270}deg)`;
      $('.gv b', el).textContent = v == null ? '--' : (Math.round(v * 10) / 10);
      $('.gs', el).textContent = g.sub(s) || '';
    });
  }

  /* ------------------------------------------------------------------ metrics polling + telemetry chart */
  let paused = false, polling = false;
  async function poll() {
    if (polling || paused) return; polling = true;
    try {
      const r = await fetch('/api/metrics?since=' + state.lastT + (state.lastT ? '' : '&limit=900'), { cache: 'no-store' });
      if (r.ok) { const j = await r.json(); j.samples.forEach(x => { state.samples.push(x); state.lastT = Math.max(state.lastT, x.t); }); if (state.samples.length > 1800) state.samples.splice(0, state.samples.length - 1800); }
    } catch (e) { /* offline: keep what we have */ }
    polling = false;
  }
  const SERIES = [
    { k: 'cpu', label: 'CPU %', color: () => css('--green'), axis: 'pct' },
    { k: 'mem', label: 'Memory %', color: () => css('--cyan'), axis: 'pct' },
    { k: 'temp', label: 'Temp °C', color: () => css('--yellow'), axis: 'pct' },
    { k: 'rx', label: 'Net ↓', color: () => css('--purple'), axis: 'rate' },
    { k: 'tx', label: 'Net ↑', color: () => css('--red'), axis: 'rate' }
  ];
  const hasData = k => state.samples.some(x => x[k] != null);

  function setupCanvas(cv) {
    const r = cv.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(10, Math.round(r.width)), h = Math.max(10, Math.round(r.height));
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    const c = cv.getContext('2d'); c.setTransform(dpr, 0, 0, dpr, 0, 0); return { c, w, h };
  }
  const chartHover = { x: null };
  function drawChart() {
    const cv = $('#deckChart'); if (!cv) return;
    const { c, w, h } = setupCanvas(cv);
    c.clearRect(0, 0, w, h);
    const pad = { l: 34, r: 46, t: 10, b: 20 }, iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
    const now = state.samples.length ? state.samples[state.samples.length - 1].t : Date.now() / 1000;
    const t0 = now - state.range, rows = state.samples.filter(x => x.t >= t0);
    const active = SERIES.filter(s => hasData(s.k) && !state.hidden[s.k]);
    // legend
    const lg = $('#deckLegend');
    const lgHtml = SERIES.filter(s => hasData(s.k)).map(s => `<button type="button" class="lgb ${state.hidden[s.k] ? 'off' : ''}" data-k="${s.k}" style="--c:${s.color()}"><i></i>${s.label}</button>`).join('');
    if (lg.dataset.h !== lgHtml) { lg.innerHTML = lgHtml; lg.dataset.h = lgHtml; $$('button', lg).forEach(b => b.onclick = () => { state.hidden[b.dataset.k] = !state.hidden[b.dataset.k]; }); }
    // grid + axes
    c.font = '10px ' + getComputedStyle(document.body).fontFamily; c.textBaseline = 'middle';
    c.strokeStyle = 'rgba(255,255,255,.07)'; c.fillStyle = 'rgba(200,220,210,.55)'; c.lineWidth = 1;
    for (let i = 0; i <= 4; i++) { const y = pad.t + ih * i / 4; c.beginPath(); c.moveTo(pad.l, y); c.lineTo(w - pad.r, y); c.stroke(); c.textAlign = 'right'; c.fillText(String(100 - i * 25), pad.l - 6, y); }
    const rateMax = Math.max(1024, ...rows.map(x => Math.max(x.rx || 0, x.tx || 0))) * 1.15;
    if (active.some(s => s.axis === 'rate')) { c.textAlign = 'left'; for (let i = 0; i <= 4; i++) c.fillText(fmtRate(rateMax * (1 - i / 4)).replace('/s', ''), w - pad.r + 6, pad.t + ih * i / 4); }
    c.textAlign = 'center'; for (let i = 0; i <= 4; i++) { const t = state.range * (1 - i / 4); c.fillText(t ? '-' + (t >= 60 ? Math.round(t / 60) + 'm' : t + 's') : 'now', pad.l + iw * i / 4, h - 6); }
    if (rows.length < 2) { c.fillStyle = 'rgba(200,220,210,.5)'; c.textAlign = 'center'; c.fillText('collecting samples...', w / 2, h / 2); return; }
    const X = t => pad.l + (t - t0) / state.range * iw;
    const Y = (v, axis) => pad.t + ih * (1 - (axis === 'rate' ? v / rateMax : v / 100));
    active.forEach(s => {
      const pts = rows.filter(x => x[s.k] != null).map(x => [X(x.t), Y(clamp(x[s.k], 0, s.axis === 'rate' ? rateMax : 100), s.axis)]); if (pts.length < 2) return;
      const col = s.color();
      const path = () => { c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length - 1; i++) { const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2; c.quadraticCurveTo(pts[i][0], pts[i][1], mx, my); } c.lineTo(pts[pts.length - 1][0], pts[pts.length - 1][1]); };
      const g = c.createLinearGradient(0, pad.t, 0, pad.t + ih); g.addColorStop(0, col + '55'); g.addColorStop(1, col + '00');
      path(); c.lineTo(pts[pts.length - 1][0], pad.t + ih); c.lineTo(pts[0][0], pad.t + ih); c.closePath(); c.fillStyle = g; c.fill();
      path(); c.strokeStyle = col; c.lineWidth = 1.8; c.lineJoin = 'round'; c.shadowColor = col; c.shadowBlur = 6; c.stroke(); c.shadowBlur = 0;
      const last = pts[pts.length - 1]; c.beginPath(); c.arc(last[0], last[1], 3, 0, TAU); c.fillStyle = col; c.fill();
    });
    // hover crosshair + tooltip
    const tip = $('#deckChartTip');
    if (chartHover.x != null && chartHover.x >= pad.l && chartHover.x <= w - pad.r) {
      const t = t0 + (chartHover.x - pad.l) / iw * state.range;
      let best = rows[0]; rows.forEach(x => { if (Math.abs(x.t - t) < Math.abs(best.t - t)) best = x; });
      const bx = X(best.t);
      c.strokeStyle = 'rgba(255,255,255,.35)'; c.setLineDash([3, 3]); c.beginPath(); c.moveTo(bx, pad.t); c.lineTo(bx, pad.t + ih); c.stroke(); c.setLineDash([]);
      active.forEach(s => { if (best[s.k] != null) { c.beginPath(); c.arc(bx, Y(clamp(best[s.k], 0, s.axis === 'rate' ? rateMax : 100), s.axis), 4, 0, TAU); c.fillStyle = s.color(); c.fill(); c.strokeStyle = '#000'; c.lineWidth = 1; c.stroke(); } });
      tip.hidden = false; tip.innerHTML = `<b>${new Date(best.t * 1000).toLocaleTimeString()}</b>` + active.filter(s => best[s.k] != null).map(s => `<span style="--c:${s.color()}"><i></i>${s.label} <em>${s.axis === 'rate' ? fmtRate(best[s.k]) : (Math.round(best[s.k] * 10) / 10)}</em></span>`).join('');
      tip.style.left = clamp(bx + 12, 4, w - 170) + 'px'; tip.style.top = '8px';
    } else tip.hidden = true;
    // stats
    const st = $('#deckStats');
    const html = active.filter(s => s.axis === 'pct').map(s => { const v = rows.map(x => x[s.k]).filter(x => x != null); if (!v.length) return ''; return `<span style="--c:${s.color()}"><i></i>${s.label} <b>now ${Math.round(v[v.length - 1])}</b> · avg ${Math.round(v.reduce((a, b) => a + b, 0) / v.length)} · peak ${Math.round(Math.max.apply(null, v))}</span>`; }).join('');
    if (st.dataset.h !== html) { st.innerHTML = html; st.dataset.h = html; }
  }

  /* ------------------------------------------------------------------ signal radar */
  const radar = { blips: [], hover: null, sweep: 0 };
  const TYPE_COL = { wifi: () => css('--green'), bt: () => css('--cyan'), lan: () => css('--yellow') };
  function radarBlips(list, w, h) {
    const cx = w / 2, cy = h / 2, R0 = Math.min(w, h) / 2 - 14;
    return list.map(d => {
      const a = hash(d.id) * TAU; let rr;
      if (d.type === 'wifi') rr = 0.14 + (1 - clamp(d.sig, 0, 100) / 100) * 0.78;
      else if (d.type === 'bt') rr = 0.3 + hash(d.id + 'r') * 0.28;
      else rr = 0.55 + hash(d.id + 'r') * 0.4;
      return { d, a, x: cx + Math.cos(a) * rr * R0, y: cy + Math.sin(a) * rr * R0, lit: 0 };
    });
  }
  function drawRadar(dt) {
    const cv = $('#deckRadar'); if (!cv) return;
    const { c, w, h } = setupCanvas(cv); c.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2, R0 = Math.min(w, h) / 2 - 14, g = css('--green');
    const { list } = devices();
    const key = list.map(d => d.id + d.sig).join('|') + w + h;
    if (radar.key !== key) { const old = new Map(radar.blips.map(b => [b.d.id, b.lit])); radar.blips = radarBlips(list, w, h); radar.blips.forEach(b => { b.lit = old.get(b.d.id) || 0; }); radar.key = key; }
    // rings + spokes
    c.lineWidth = 1;
    for (let i = 1; i <= 4; i++) { c.beginPath(); c.arc(cx, cy, R0 * i / 4, 0, TAU); c.strokeStyle = 'rgba(255,255,255,.09)'; c.stroke(); }
    for (let i = 0; i < 12; i++) { const a = i * TAU / 12; c.beginPath(); c.moveTo(cx, cy); c.lineTo(cx + Math.cos(a) * R0, cy + Math.sin(a) * R0); c.strokeStyle = 'rgba(255,255,255,.05)'; c.stroke(); }
    c.fillStyle = 'rgba(200,220,210,.4)'; c.font = '9px ' + getComputedStyle(document.body).fontFamily; c.textAlign = 'left'; c.textBaseline = 'middle';
    ['strong', '', '', 'weak'].forEach((t, i) => t && c.fillText(t, cx + 4, cy - R0 * (i + 1) / 4 + 8));
    // sweep
    radar.sweep = (radar.sweep + dt * 1.1) % TAU;
    const sw = radar.sweep;
    const cone = c.createConicGradient ? c.createConicGradient(sw - 1.2, cx, cy) : null;
    if (cone) { cone.addColorStop(0, g + '00'); cone.addColorStop(1.2 / TAU, g + '55'); cone.addColorStop(1.2 / TAU + 0.001, g + '00'); c.beginPath(); c.moveTo(cx, cy); c.arc(cx, cy, R0, 0, TAU); c.fillStyle = cone; c.fill(); }
    c.beginPath(); c.moveTo(cx, cy); c.lineTo(cx + Math.cos(sw) * R0, cy + Math.sin(sw) * R0); c.strokeStyle = g; c.lineWidth = 2; c.shadowColor = g; c.shadowBlur = 10; c.stroke(); c.shadowBlur = 0;
    // blips
    radar.blips.forEach(b => {
      let diff = (sw - b.a) % TAU; if (diff < 0) diff += TAU;
      if (diff < dt * 1.1 + 0.06) b.lit = 1; else b.lit = Math.max(0, b.lit - dt * 0.28);
      const col = TYPE_COL[b.d.type](), rad = 3 + b.d.sig / 100 * 4.5, base = 0.28 + b.lit * 0.72;
      if (b.lit > 0.05) { c.beginPath(); c.arc(b.x, b.y, rad + 6 * b.lit + 2, 0, TAU); c.fillStyle = col + Math.round(b.lit * 60).toString(16).padStart(2, '0'); c.fill(); }
      c.beginPath(); c.arc(b.x, b.y, rad, 0, TAU); c.globalAlpha = base; c.fillStyle = col; c.fill(); c.globalAlpha = 1;
      if (b.d.on) { c.beginPath(); c.arc(b.x, b.y, rad + 3, 0, TAU); c.strokeStyle = col; c.lineWidth = 1; c.stroke(); }
      if (state.selected === b.d.id || (radar.hover && radar.hover.d.id === b.d.id)) { c.beginPath(); c.arc(b.x, b.y, rad + 7, 0, TAU); c.strokeStyle = '#fff'; c.lineWidth = 1.5; c.stroke(); }
    });
    // you are here
    c.beginPath(); c.arc(cx, cy, 4, 0, TAU); c.fillStyle = '#fff'; c.fill();
    if (!list.length) { c.fillStyle = 'rgba(200,220,210,.6)'; c.textAlign = 'center'; c.font = '12px ' + getComputedStyle(document.body).fontFamily; c.fillText('No signals yet. Run a scan, or turn on Demo data.', cx, cy + R0 * 0.6); }
    const tip = $('#deckRadarTip');
    if (radar.hover) { const d = radar.hover.d; tip.hidden = false; tip.innerHTML = `<b>${esc(d.name)}</b><span>${d.type.toUpperCase()} · ${esc(d.sub)}</span><span>signal ${d.sig}%</span>`; tip.style.left = clamp(radar.hover.x + 12, 4, w - 170) + 'px'; tip.style.top = clamp(radar.hover.y - 10, 4, h - 60) + 'px'; } else tip.hidden = true;
  }

  /* ------------------------------------------------------------------ Wi-Fi spectrum */
  function drawSpectrum() {
    const cv = $('#deckSpectrum'); if (!cv) return;
    const { c, w, h } = setupCanvas(cv); c.clearRect(0, 0, w, h);
    const { list } = devices(), wifi = list.filter(d => d.type === 'wifi' && d.ch);
    const pad = { l: 30, r: 10, t: 8, b: 22 }, iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
    const n24 = wifi.filter(d => d.ch <= 14), n5 = wifi.filter(d => d.ch > 14);
    c.font = '10px ' + getComputedStyle(document.body).fontFamily; c.fillStyle = 'rgba(200,220,210,.55)'; c.strokeStyle = 'rgba(255,255,255,.07)'; c.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) { const y = pad.t + ih * i / 4; c.beginPath(); c.moveTo(pad.l, y); c.lineTo(w - pad.r, y); c.stroke(); c.textAlign = 'right'; c.fillText(String(100 - i * 25), pad.l - 5, y); }
    const X = ch => pad.l + (ch - 0) / 15 * iw; // channels -1..14 mapped 0..15
    c.textAlign = 'center'; for (let ch = 1; ch <= 14; ch++) c.fillText(String(ch), X(ch), h - 8);
    const sorted = n24.slice().sort((a, b) => a.sig - b.sig);
    sorted.forEach((d, i) => {
      const hue = Math.round(hash(d.name) * 300 + 20), col = `hsl(${hue} 85% 60%)`, x0 = X(d.ch - 2), x1 = X(d.ch + 2), xm = X(d.ch), yt = pad.t + ih * (1 - d.sig / 100), yb = pad.t + ih;
      c.beginPath(); c.moveTo(x0, yb); c.bezierCurveTo(x0 + (xm - x0) * 0.6, yb, xm - (xm - x0) * 0.5, yt, xm, yt); c.bezierCurveTo(xm + (x1 - xm) * 0.5, yt, x1 - (x1 - xm) * 0.6, yb, x1, yb);
      c.fillStyle = `hsl(${hue} 85% 60% / .22)`; c.fill(); c.strokeStyle = col; c.lineWidth = d.on ? 2.6 : 1.4; c.stroke();
      c.fillStyle = col; c.textAlign = 'center'; c.fillText(d.name.length > 14 ? d.name.slice(0, 13) + '…' : d.name, xm, Math.max(pad.t + 8, yt - 8 - (i % 2) * 0));
      c.fillStyle = 'rgba(200,220,210,.55)';
    });
    $('#deckSpectrumNote').textContent = !wifi.length ? 'No Wi-Fi networks with channel data yet.' : `${n24.length} on 2.4 GHz` + (n5.length ? ` · ${n5.length} on 5 GHz (ch ${n5.map(d => d.ch).join(', ')})` : '') + ' · overlapping curves = co-channel interference';
  }

  /* ------------------------------------------------------------------ network graph (force-directed) */
  const graph = { nodes: [], links: [], key: '', drag: null, hover: null };
  function buildGraph(w, h) {
    const { list } = devices();
    const key = list.map(d => d.id).join('|');
    if (graph.key === key) return; graph.key = key;
    const old = new Map(graph.nodes.map(n => [n.id, n]));
    const host = old.get('host') || { id: 'host', label: (status() && status().system && status().system.hostname) || 'this host', type: 'host', x: w / 2, y: h / 2, vx: 0, vy: 0, r: 15, fixed: true };
    host.x = w / 2; host.y = h / 2; host.fixed = true;
    graph.nodes = [host]; graph.links = [];
    list.forEach(d => {
      const o = old.get(d.id);
      const n = o || { id: d.id, x: w / 2 + (hash(d.id) - .5) * w * .6, y: h / 2 + (hash(d.id + 'y') - .5) * h * .6, vx: 0, vy: 0 };
      Object.assign(n, { label: d.name, type: d.type, r: d.type === 'lan' ? 9 : d.type === 'wifi' ? 7 : 6, on: d.on, sig: d.sig, ref: d }); graph.nodes.push(n);
      graph.links.push({ a: host, b: n, on: d.on, len: 70 + (100 - d.sig) * 0.9 });
    });
  }
  function stepGraph(dt, w, h) {
    const N = graph.nodes, k = Math.min(dt, 0.033) * 60;
    for (let i = 0; i < N.length; i++) for (let j = i + 1; j < N.length; j++) {
      const a = N[i], b = N[j]; let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy + 0.01, d = Math.sqrt(d2), f = 1400 / d2;
      dx /= d; dy /= d; if (!a.fixed) { a.vx -= dx * f * k; a.vy -= dy * f * k; } if (!b.fixed) { b.vx += dx * f * k; b.vy += dy * f * k; }
    }
    graph.links.forEach(l => { const dx = l.b.x - l.a.x, dy = l.b.y - l.a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - l.len) * 0.02 * k; if (!l.b.fixed) { l.b.vx -= dx / d * f; l.b.vy -= dy / d * f; } });
    N.forEach(n => { if (n.fixed || n === graph.drag) return; n.vx *= 0.86; n.vy *= 0.86; n.x = clamp(n.x + n.vx, 26, w - 26); n.y = clamp(n.y + n.vy, 24, h - 30); });
  }
  function drawGraph(dt) {
    const cv = $('#deckGraph'); if (!cv) return;
    const { c, w, h } = setupCanvas(cv); c.clearRect(0, 0, w, h);
    buildGraph(w, h); stepGraph(dt, w, h);
    const t = performance.now() / 1000;
    graph.links.forEach(l => {
      const col = TYPE_COL[l.b.type](); c.beginPath(); c.moveTo(l.a.x, l.a.y); c.lineTo(l.b.x, l.b.y);
      c.strokeStyle = col + (l.on ? 'aa' : '44'); c.lineWidth = l.on ? 1.6 : 1; c.setLineDash(l.on ? [] : [4, 4]); c.stroke(); c.setLineDash([]);
      if (l.on) { const p = (t * 0.5 + hash(l.b.id)) % 1; c.beginPath(); c.arc(l.a.x + (l.b.x - l.a.x) * p, l.a.y + (l.b.y - l.a.y) * p, 2, 0, TAU); c.fillStyle = '#fff'; c.fill(); }
    });
    graph.nodes.forEach(n => {
      const col = n.type === 'host' ? css('--purple') : TYPE_COL[n.type](), hot = graph.hover === n || graph.drag === n || state.selected === n.id;
      const glow = c.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r * (hot ? 4 : 2.6)); glow.addColorStop(0, col + '88'); glow.addColorStop(1, col + '00');
      c.fillStyle = glow; c.beginPath(); c.arc(n.x, n.y, n.r * (hot ? 4 : 2.6), 0, TAU); c.fill();
      c.beginPath(); c.arc(n.x, n.y, n.r, 0, TAU); c.fillStyle = col; c.fill(); c.strokeStyle = '#fff'; c.lineWidth = hot ? 2 : 1; c.stroke();
      if (n.type === 'host') { c.fillStyle = '#fff'; c.font = 'bold 10px ' + getComputedStyle(document.body).fontFamily; c.textAlign = 'center'; c.fillText(String(n.label).slice(0, 14), n.x, n.y + n.r + 12); }
      else if (hot || n.type === 'lan') { c.fillStyle = 'rgba(230,245,235,.85)'; c.font = '9.5px ' + getComputedStyle(document.body).fontFamily; c.textAlign = 'center'; c.fillText(String(n.label).slice(0, 16), n.x, n.y + n.r + 11); }
    });
    const tip = $('#deckGraphTip');
    if (graph.hover && graph.hover.ref) { const d = graph.hover.ref; tip.hidden = false; tip.innerHTML = `<b>${esc(d.name)}</b><span>${d.type.toUpperCase()} · ${esc(d.sub)}</span>`; tip.style.left = clamp(graph.hover.x + 14, 4, w - 170) + 'px'; tip.style.top = clamp(graph.hover.y - 8, 4, h - 50) + 'px'; } else tip.hidden = true;
  }

  /* ------------------------------------------------------------------ tables, rings, timeline, pulse */
  const sigBars = v => { const l = v >= 75 ? 4 : v >= 50 ? 3 : v >= 25 ? 2 : v > 0 ? 1 : 0; return `<span class="sb" title="${v}%">${[1, 2, 3, 4].map(i => `<i class="${i <= l ? 'on' : ''}" style="height:${4 + i * 3}px"></i>`).join('')}</span>`; };
  function renderDevices() {
    const t = $('#deckDevTable'); if (!t) return;
    const { list, isDemo } = devices(); const badge = $('#deckDemoBadge'); badge.hidden = !isDemo; $('#deckDemoBtn b').textContent = demo ? 'on' : 'off';
    let rows = list.filter(d => (state.filter === 'all' || d.type === state.filter) && (!state.search || (d.name + d.sub).toLowerCase().includes(state.search)));
    const { k, dir } = state.sort; rows.sort((a, b) => (k === 'name' ? a.name.localeCompare(b.name) : k === 'type' ? a.type.localeCompare(b.type) : a.sig - b.sig) * dir);
    const arrow = key => (state.sort.k === key ? (state.sort.dir > 0 ? ' ▲' : ' ▼') : '');
    t.innerHTML = `<thead><tr><th data-k="type">Type${arrow('type')}</th><th data-k="name">Name${arrow('name')}</th><th>Detail</th><th data-k="sig">Signal${arrow('sig')}</th></tr></thead><tbody>` +
      (rows.length ? rows.map(d => `<tr data-id="${esc(d.id)}" class="${state.selected === d.id ? 'sel' : ''}"><td><span class="tag ${d.type}">${d.type}</span></td><td>${d.on ? '<i class="dot on"></i>' : ''}${esc(d.name)}</td><td class="dim">${esc(d.sub)}</td><td>${sigBars(d.sig)}</td></tr>`).join('') : '<tr><td colspan="4" class="dim">Nothing matches. Run a scan from the Signals tab.</td></tr>') + '</tbody>';
  }
  function renderProcs() {
    const t = $('#deckProcTable'); if (!t) return; const s = status(); const procs = (s && s.system && s.system.top_processes) || [];
    if (!procs.length) { t.innerHTML = '<tbody><tr><td class="dim">No process data on this host.</td></tr></tbody>'; return; }
    const cpu = p => num(p.cpu) || 0, mem = p => num(String(p.memory).replace(/[^\d.]/g, '')) || 0;
    const haveCpu = procs.some(p => num(p.cpu) != null);
    const key = state.psort === 'cpu' && haveCpu ? cpu : mem;
    const rows = procs.slice().sort((a, b) => key(b) - key(a)).slice(0, 10);
    const maxC = Math.max(1, ...rows.map(cpu)), maxM = Math.max(1, ...rows.map(mem));
    const bar = (v, max) => `<span class="mb"><i style="width:${(v / max * 100).toFixed(0)}%"></i></span>`;
    t.innerHTML = '<thead><tr><th>PID</th><th>Command</th><th>CPU</th><th>Memory</th></tr></thead><tbody>' + rows.map(p => `<tr><td class="dim">${esc(p.pid)}</td><td>${esc(p.command)}</td><td>${haveCpu ? bar(cpu(p), maxC) + ' ' : ''}${esc(p.cpu)}</td><td>${bar(mem(p), maxM)} ${esc(p.memory)}</td></tr>`).join('') + '</tbody>';
  }
  function renderRings() {
    const el = $('#deckRings'); const s = status(); const disks = (s && s.system && s.system.disk_all) || [];
    if (!disks.length) { el.innerHTML = '<div class="dim">No disk data.</div>'; return; }
    const r = 30, C2 = 2 * Math.PI * r;
    el.innerHTML = disks.slice(0, 8).map(d => { const m = /(\d+)%/.exec(d.use_percent || ''); const p = m ? +m[1] : 0; const st = p >= 93 ? 'bad' : p >= 80 ? 'warn' : 'ok';
      return `<div class="ring" data-state="${st}"><svg viewBox="0 0 80 80"><circle class="rt" cx="40" cy="40" r="${r}"/><circle class="rv" cx="40" cy="40" r="${r}" stroke-dasharray="${C2 * p / 100} ${C2}" transform="rotate(-90 40 40)"/></svg><b>${p}%</b><span>${esc(d.mount)}</span><small>${esc(d.used)} / ${esc(d.size)}</small></div>`; }).join('');
  }
  const EV_ICON = { alert: '⚠', service: '⚙', thermal: '♨', gps: '⌖', vpn: '⛨', vision: '◉', boot: '⏻', scan: '⌁', settings: '☰', chatter: '…', lab: '⚗', spicy: '✦' };
  const EV_CLASS = { alert: 'bad', service: 'warn', thermal: 'warn', boot: 'ok', vpn: 'info', gps: 'info' };
  let lastEvKey = '';
  function renderEvents() {
    const ol = $('#deckTimeline'); if (!ol) return; const s = status(); let ev = (s && s.events) || [];
    if (state.evFilter !== 'all') ev = ev.filter(e => (state.evFilter === 'chatter' ? ['chatter', 'atmosphere'].includes(e.kind) : e.kind === state.evFilter));
    ev = ev.slice(0, 30); const key = state.evFilter + JSON.stringify(ev.map(e => e.ts + e.kind)); if (key === lastEvKey) return; lastEvKey = key;
    ol.innerHTML = ev.length ? ev.map(e => `<li class="${EV_CLASS[e.kind] || ''}"><i>${EV_ICON[e.kind] || '•'}</i><div><b>${esc(e.kind)}</b><span>${esc(e.text)}</span></div><time>${new Date(e.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time></li>`).join('') : '<li class="dim">No events yet.</li>';
  }
  function renderPosture() {
    const el = $('#deckPosture'); const s = status(); const a = s && s.alert; if (!a) { el.innerHTML = '<div class="dim">Alert engine warming up.</div>'; return; }
    const L = a.layers || {}, cnt = k => (L[k] || []).length;
    el.innerHTML = `<div class="lvl ${(a.level || '').toLowerCase()}"><b>${esc(a.level || 'n/a')}</b><small>score ${a.score != null ? a.score : 0}</small></div><div class="lay"><span class="u">${cnt('urgent')}<small>urgent</small></span><span class="a">${cnt('advisory')}<small>advisory</small></span><span class="h">${cnt('hygiene')}<small>hygiene</small></span></div><div class="dim">${esc((a.reasons || []).slice(0, 2).join(' · '))}</div>`;
  }
  let pulseT = 0;
  function drawPulse(dt) {
    const cv = $('#deckPulse'); if (!cv) return; const { c, w, h } = setupCanvas(cv); c.clearRect(0, 0, w, h);
    const last = state.samples[state.samples.length - 1] || {}, load = clamp((last.cpu || 8) / 100, .04, 1); pulseT += dt * (1 + load * 2.4);
    const g = css('--green'); c.strokeStyle = g; c.lineWidth = 2; c.shadowColor = g; c.shadowBlur = 8; c.beginPath();
    for (let x = 0; x <= w; x += 2) {
      const ph = ((x / 90) - pulseT * 1.4) % 1, p = ph < 0 ? ph + 1 : ph; let y = 0;
      if (p > .42 && p < .46) y = -(p - .42) / .04; else if (p >= .46 && p < .5) y = -1 + (p - .46) / .04 * 1.4; else if (p >= .5 && p < .54) y = .4 - (p - .5) / .04 * .4; else if (p > .62 && p < .74) y = -.22 * Math.sin((p - .62) / .12 * Math.PI);
      y += Math.sin(x * .05 + pulseT * 3) * .02;
      const py = h / 2 + y * (h * (.22 + load * .3)); x ? c.lineTo(x, py) : c.moveTo(x, py);
    }
    c.stroke(); c.shadowBlur = 0;
    c.fillStyle = 'rgba(200,220,210,.6)'; c.font = '10px ' + getComputedStyle(document.body).fontFamily; c.textAlign = 'right'; c.fillText(Math.round(load * 100) + '% load', w - 6, 12);
  }

  /* ------------------------------------------------------------------ interaction (hover / drag) */
  function hookPointer() {
    const rel = (e, cv) => { const r = cv.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    const ch = $('#deckChart'); ch.addEventListener('pointermove', e => { chartHover.x = rel(e, ch).x; }); ch.addEventListener('pointerleave', () => { chartHover.x = null; });
    const rd = $('#deckRadar'); rd.addEventListener('pointermove', e => { const p = rel(e, rd); let best = null, bd = 16; radar.blips.forEach(b => { const d = Math.hypot(b.x - p.x, b.y - p.y); if (d < bd) { bd = d; best = b; } }); radar.hover = best ? { d: best.d, x: best.x, y: best.y } : null; rd.style.cursor = best ? 'pointer' : 'default'; });
    rd.addEventListener('pointerleave', () => { radar.hover = null; });
    rd.addEventListener('click', () => { if (radar.hover) { state.selected = state.selected === radar.hover.d.id ? null : radar.hover.d.id; renderDevices(); } });
    const gr = $('#deckGraph'); const pick = p => graph.nodes.find(n => Math.hypot(n.x - p.x, n.y - p.y) < n.r + 8);
    gr.addEventListener('pointerdown', e => { const n = pick(rel(e, gr)); if (n && !n.fixed) { graph.drag = n; gr.setPointerCapture(e.pointerId); } });
    gr.addEventListener('pointermove', e => { const p = rel(e, gr); if (graph.drag) { graph.drag.x = p.x; graph.drag.y = p.y; graph.drag.vx = graph.drag.vy = 0; } graph.hover = pick(p) || null; gr.style.cursor = graph.hover ? (graph.hover.fixed ? 'default' : 'grab') : 'default'; });
    gr.addEventListener('pointerup', () => { graph.drag = null; }); gr.addEventListener('pointerleave', () => { graph.hover = null; });
  }

  /* ------------------------------------------------------------------ loop */
  let raf = 0, last = 0, lastSlow = 0, lastStatusRef = null, lastPoll = 0;
  function refreshAll(force) { renderGauges(); renderDevices(); renderProcs(); renderRings(); renderEvents(); renderPosture(); if (force) { radar.key = ''; graph.key = ''; } }
  function frame(ts) {
    raf = 0;
    if (document.body.dataset.activeTab !== 'deck' || document.hidden) { raf = requestAnimationFrame(frame); return; }
    const dt = last ? Math.min((ts - last) / 1000, .05) : .016; last = ts;
    const s = status();
    if (s !== lastStatusRef) { lastStatusRef = s; refreshAll(false); }
    if (ts - lastPoll > 2000) { lastPoll = ts; poll(); }
    if (ts - lastSlow > 1000) { lastSlow = ts; renderEvents(); }
    if (!paused) { drawChart(); }
    drawRadar(paused ? 0 : dt); drawSpectrum(); drawGraph(paused ? 0 : dt); drawPulse(paused ? 0 : dt);
    raf = requestAnimationFrame(frame);
  }

  function boot() {
    build(); if (!built) return;
    buildGauges(); hookPointer(); refreshAll(true);
    poll(); raf = requestAnimationFrame(frame);
    (window.v2ExtraCommands = window.v2ExtraCommands || []).push(() => [
      { g: '◈', grp: 'Deck', name: 'Deck: toggle demo data', run: () => { demo = !demo; store.set('deckDemo', demo ? '1' : '0'); refreshAll(true); if (window.v2Toast) window.v2Toast('Deck', 'demo data ' + (demo ? 'on' : 'off'), 'info', 1600); } },
      { g: '◈', grp: 'Deck', name: 'Go to Deck', hint: '2', run: () => { if (typeof showTab === 'function') showTab('deck'); } }
    ]);
  }
  window.spac3Deck = { setDemo: v => { demo = !!v; store.set('deckDemo', demo ? '1' : '0'); refreshAll(true); }, state };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
