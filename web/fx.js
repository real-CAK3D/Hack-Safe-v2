/* Spac3-Gh0st visual FX + console: constellation background, card spotlight, 3D tilt,
   boot sequence and a drop-down terminal (press ` or ~). Everything is optional and cheap:
   the background pauses when the tab is hidden and all motion is off under prefers-reduced-motion. */
(function () {
  'use strict';

  const $ = (s, r) => (r || document).querySelector(s);
  const store = { get: (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
  const status = () => { try { return typeof lastStatus !== 'undefined' ? lastStatus : null; } catch (e) { return null; } };
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const REDUCED = (() => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; } })();
  const toast = (a, b, c, d) => { if (window.v2Toast) window.v2Toast(a, b, c, d); };

  /* ------------------------------------------------------------------ constellation background */
  const bg = { on: store.get('fxBg', REDUCED ? '0' : '1') === '1', cv: null, ctx: null, pts: [], w: 0, h: 0, mx: -999, my: -999, raf: 0, last: 0 };
  function bgInit() {
    if (bg.cv) return;
    const cv = document.createElement('canvas'); cv.id = 'fxBg'; cv.setAttribute('aria-hidden', 'true');
    cv.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.7';
    document.body.insertBefore(cv, document.body.firstChild); bg.cv = cv; bg.ctx = cv.getContext('2d');
    window.addEventListener('resize', bgResize); bgResize();
    window.addEventListener('pointermove', e => { bg.mx = e.clientX; bg.my = e.clientY; }, { passive: true });
  }
  function bgResize() {
    const dpr = Math.min(devicePixelRatio || 1, 1.5); bg.w = innerWidth; bg.h = innerHeight;
    bg.cv.width = bg.w * dpr; bg.cv.height = bg.h * dpr; bg.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = Math.round(Math.min(70, bg.w * bg.h / 26000)); bg.pts = [];
    for (let i = 0; i < n; i++) bg.pts.push({ x: Math.random() * bg.w, y: Math.random() * bg.h, vx: (Math.random() - .5) * 18, vy: (Math.random() - .5) * 18, r: .8 + Math.random() * 1.4 });
  }
  function bgFrame(ts) {
    bg.raf = 0; if (!bg.on) return;
    if (document.hidden) { bg.raf = requestAnimationFrame(bgFrame); return; }
    if (ts - bg.last < 33) { bg.raf = requestAnimationFrame(bgFrame); return; }  // ~30fps: O(n^2) link pass every frame adds up
    const dt = bg.last ? Math.min((ts - bg.last) / 1000, .05) : .016; bg.last = ts;
    const c = bg.ctx, col = getComputedStyle(document.body).getPropertyValue('--green').trim() || '#27c93f', L = 130;
    c.clearRect(0, 0, bg.w, bg.h);
    for (const p of bg.pts) {
      p.x += p.vx * dt; p.y += p.vy * dt; if (p.x < 0 || p.x > bg.w) p.vx *= -1; if (p.y < 0 || p.y > bg.h) p.vy *= -1;
      const dx = bg.mx - p.x, dy = bg.my - p.y, d = Math.hypot(dx, dy); if (d < 160 && d > 1) { p.x += dx / d * 14 * dt; p.y += dy / d * 14 * dt; }
    }
    c.lineWidth = 1;
    for (let i = 0; i < bg.pts.length; i++) {
      const a = bg.pts[i];
      for (let j = i + 1; j < bg.pts.length; j++) { const b = bg.pts[j], d = Math.hypot(a.x - b.x, a.y - b.y); if (d < L) { c.strokeStyle = col + Math.round((1 - d / L) * 70).toString(16).padStart(2, '0'); c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y); c.stroke(); } }
      const dm = Math.hypot(a.x - bg.mx, a.y - bg.my); if (dm < 170) { c.strokeStyle = col + Math.round((1 - dm / 170) * 130).toString(16).padStart(2, '0'); c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(bg.mx, bg.my); c.stroke(); }
      c.fillStyle = col + 'cc'; c.beginPath(); c.arc(a.x, a.y, a.r, 0, 6.2832); c.fill();
    }
    bg.raf = requestAnimationFrame(bgFrame);
  }
  function setBg(on, quiet) {
    bg.on = on; store.set('fxBg', on ? '1' : '0');
    if (on) { bgInit(); bg.cv.style.display = ''; if (!bg.raf) bg.raf = requestAnimationFrame(bgFrame); } else if (bg.cv) { bg.cv.style.display = 'none'; }
    if (!quiet) toast('Background FX', on ? 'on' : 'off', 'info', 1500);
  }

  /* ------------------------------------------------------------------ card spotlight + tilt */
  function pointerFx() {
    let raf = 0, ev = null;
    document.addEventListener('pointermove', e => { ev = e; if (!raf) raf = requestAnimationFrame(apply); }, { passive: true });
    function apply() {
      raf = 0; if (!ev) return; const t = ev.target && ev.target.closest ? ev.target : null; if (!t) return;
      const card = t.closest('.card');
      if (card) { const r = card.getBoundingClientRect(); card.style.setProperty('--mx', (ev.clientX - r.left) + 'px'); card.style.setProperty('--my', (ev.clientY - r.top) + 'px'); }
      if (REDUCED) return;
      const tile = t.closest('.v2-tile, .deck-gauge');
      if (tile) { const r = tile.getBoundingClientRect(), px = (ev.clientX - r.left) / r.width - .5, py = (ev.clientY - r.top) / r.height - .5; tile.style.transform = `perspective(600px) rotateX(${(-py * 9).toFixed(2)}deg) rotateY(${(px * 11).toFixed(2)}deg) translateY(-2px)`; tile._tilt = true; }
    }
    document.addEventListener('pointerout', e => { const tile = e.target.closest && e.target.closest('.v2-tile, .deck-gauge'); if (tile && tile._tilt && !tile.contains(e.relatedTarget)) { tile.style.transform = ''; tile._tilt = false; } });
  }

  /* ------------------------------------------------------------------ boot sequence */
  function bootSeq() {
    if (REDUCED || sessionStorage.getItem('spac3Booted')) return;
    try { sessionStorage.setItem('spac3Booted', '1'); } catch (e) { /* ignore */ }
    const ov = document.createElement('div'); ov.className = 'fx-boot';
    ov.innerHTML = '<pre></pre><div class="fx-boot-hint">click or press any key to skip</div>'; document.body.appendChild(ov);
    const pre = $('pre', ov);
    const lines = ['SPAC3-GH0ST // secure companion', '> mounting sensors ............ ok', '> loading native plugins ....... ok', '> bringing up telemetry ........ ok', '> linking signals .............. ok', '> ghost online. welcome back.'];
    fetch('/api/health', { cache: 'no-store' }).then(r => r.json()).then(h => { lines[0] = 'SPAC3-GH0ST v' + h.version + ' // ' + h.plugins.loaded + ' plugins'; }).catch(() => { });
    let i = 0, ch = 0, done = false;
    const finish = () => { if (done) return; done = true; ov.classList.add('out'); setTimeout(() => ov.remove(), 500); document.removeEventListener('keydown', finish); };
    ov.addEventListener('click', finish); document.addEventListener('keydown', finish);
    (function type() {
      if (done) return; if (i >= lines.length) { setTimeout(finish, 450); return; }
      const line = lines[i]; pre.textContent = lines.slice(0, i).join('\n') + (i ? '\n' : '') + line.slice(0, ++ch) + '▌';
      if (ch >= line.length) { i++; ch = 0; setTimeout(type, 140); } else setTimeout(type, 13);
    })();
  }

  /* ------------------------------------------------------------------ console */
  let term = null, hist = [], hi = 0;
  const TABNAMES = { dash: 'dash', dashboard: 'dash', deck: 'deck', systems: 'systems', signals: 'signals', lab: 'lab', externals: 'externals', settings: 'settings' };
  function out(html, cls) { const o = $('.fx-term-out', term); const d = document.createElement('div'); d.className = cls || ''; d.innerHTML = html; o.appendChild(d); o.scrollTop = o.scrollHeight; }
  const dur = s => { const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return (d ? d + 'd ' : '') + h + 'h ' + m + 'm'; };
  const COMMANDS = {
    help: () => out('<b>commands</b>: status · health · top · uptime · net · wifi · bt · lan · scan &lt;wifi|lan|bt&gt; · theme &lt;name|next&gt; · weather &lt;preset|live&gt; · goto &lt;tab&gt; · bg &lt;on|off&gt; · crt · demo &lt;on|off&gt; · export · clear · exit'),
    status: () => { const s = status(); if (!s) return out('no status yet', 'err'); const m = s.mood || {}; out(`mood <b>${esc(m.name)}</b> ${esc(m.face)}<br>${esc(s.thought || '')}<br>alert <b>${esc((s.alert || {}).level || 'n/a')}</b> · wifi ${(s.wifi.networks || []).length} · bt ${(s.bluetooth.devices || []).length} · lan ${(s.lan.devices || []).length}`); },
    health: async () => { try { const h = await (await fetch('/api/health', { cache: 'no-store' })).json(); out(`ok · v${h.version} · server up ${dur(h.uptime_s)} · plugins ${h.plugins.loaded}/${h.plugins.total} · ${esc(h.platform.os)} ${esc(h.platform.machine)}`); } catch (e) { out('server unreachable', 'err'); } },
    uptime: () => { const s = status(), u = s && s.system && s.system.uptime_s; out(u != null ? 'host up ' + dur(u) : 'n/a'); },
    top: () => { const p = (((status() || {}).system || {}).top_processes) || []; out(p.length ? '<pre>' + p.slice(0, 8).map(x => `${String(x.pid).padEnd(7)}${String(x.command).padEnd(24)}cpu ${String(x.cpu).padEnd(6)}mem ${x.memory}`).join('\n') + '</pre>' : 'no process data', p.length ? '' : 'err'); },
    net: () => { const n = ((status() || {}).system || {}).net_io; out(n && n.available ? `rx ${(n.rx_bps / 1024).toFixed(1)} KB/s · tx ${(n.tx_bps / 1024).toFixed(1)} KB/s` : 'no interface counters', n && n.available ? '' : 'err'); },
    wifi: () => { const w = ((status() || {}).wifi || {}).networks || []; out(w.length ? '<pre>' + w.slice(0, 12).map(n => `${String(n.ssid).padEnd(26)}ch ${String(n.channel).padEnd(4)}${String(n.signal).padStart(3)}%  ${n.security}`).join('\n') + '</pre>' : 'no networks (try: scan wifi)', w.length ? '' : 'err'); },
    bt: () => { const b = ((status() || {}).bluetooth || {}).devices || []; out(b.length ? b.map(d => `${esc(d.name)} <i>${esc(d.mac)}</i>`).join('<br>') : 'no devices', b.length ? '' : 'err'); },
    lan: () => { const l = ((status() || {}).lan || {}).devices || []; out(l.length ? '<pre>' + l.slice(0, 14).map(d => `${String(d.ip).padEnd(16)}${String(d.mac || '').padEnd(19)}${d.vendor || ''}`).join('\n') + '</pre>' : 'no devices', l.length ? '' : 'err'); },
    scan: async a => { const k = { wifi: 'wifi', lan: 'lan', bt: 'bluetooth', bluetooth: 'bluetooth' }[a[0]]; if (!k) return out('usage: scan wifi|lan|bt', 'err'); out('scanning ' + k + '...'); try { await fetch('/api/scan/' + k, { cache: 'no-store' }); if (typeof refresh === 'function') await refresh(); out('done. run <b>' + a[0] + '</b> to see results'); } catch (e) { out('scan failed', 'err'); } },
    theme: a => { const list = ['default', 'aurora', 'synthwave', 'glacier', 'mono', 'purple', 'blue', 'orange', 'red', 'yellow']; let t = a[0]; if (!t || t === 'next') t = list[(list.indexOf(document.body.dataset.theme || 'default') + 1) % list.length]; if (!list.includes(t)) return out('themes: ' + list.join(', '), 'err'); if (typeof applyTheme === 'function') applyTheme(t); else document.body.dataset.theme = t; out('theme → <b>' + esc(t) + '</b>'); },
    weather: a => { const fx = window.spac3WeatherFX; if (!fx) return out('weather engine not loaded', 'err'); const name = a.join(' '); if (!name) return out('presets: ' + fx.presets.join(', ') + ', live'); const hit = fx.presets.find(p => p.toLowerCase() === name.toLowerCase()) || (name === 'live' ? 'live' : null); if (!hit || !fx.preview(hit)) return out('unknown preset', 'err'); out('weather → <b>' + esc(hit) + '</b>'); },
    goto: a => { const t = TABNAMES[(a[0] || '').toLowerCase()]; if (!t) return out('tabs: ' + Object.keys(TABNAMES).join(', '), 'err'); if (typeof showTab === 'function') showTab(t); out('→ ' + t); },
    bg: a => { setBg(a[0] ? a[0] === 'on' : !bg.on, true); out('background fx ' + (bg.on ? 'on' : 'off')); },
    crt: () => { document.body.classList.toggle('v2-crt'); out('crt scanlines ' + (document.body.classList.contains('v2-crt') ? 'on' : 'off')); },
    demo: a => { if (!window.spac3Deck) return out('deck not loaded', 'err'); window.spac3Deck.setDemo(a[0] ? a[0] === 'on' : true); out('deck demo data ' + (a[0] === 'off' ? 'off' : 'on')); },
    export: () => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })); out('use the palette entry "Export status snapshot"'); },
    clear: () => { $('.fx-term-out', term).innerHTML = ''; },
    exit: () => toggleTerm(false)
  };
  function buildTerm() {
    term = document.createElement('div'); term.className = 'fx-term'; term.setAttribute('role', 'dialog'); term.setAttribute('aria-label', 'Ghost console');
    term.innerHTML = '<div class="fx-term-out"></div><div class="fx-term-line"><span>ghost@spac3 ❯</span><input type="text" spellcheck="false" autocomplete="off" aria-label="console input"></div>';
    document.body.appendChild(term);
    out('Spac3-Gh0st console. type <b>help</b>. press <b>`</b> to close.');
    const inp = $('input', term);
    inp.addEventListener('keydown', async e => {
      if (e.key === 'Enter') { const line = inp.value.trim(); inp.value = ''; if (!line) return; hist.push(line); hi = hist.length; out('<span class="p">❯</span> ' + esc(line), 'cmd'); const [cmd, ...args] = line.split(/\s+/); const fn = COMMANDS[cmd.toLowerCase()]; if (!fn) out('unknown command: ' + esc(cmd) + ' (try help)', 'err'); else { try { await fn(args); } catch (err) { out('error: ' + esc(err.message || err), 'err'); } } }
      else if (e.key === 'ArrowUp') { if (hi > 0) inp.value = hist[--hi]; e.preventDefault(); }
      else if (e.key === 'ArrowDown') { hi = Math.min(hi + 1, hist.length); inp.value = hist[hi] || ''; e.preventDefault(); }
      else if (e.key === 'Escape' || (e.key === '`' && !inp.value)) { toggleTerm(false); e.preventDefault(); }
      else if (e.key === 'Tab') { const p = inp.value.trim(); const m = Object.keys(COMMANDS).filter(c => c.startsWith(p)); if (m.length === 1) inp.value = m[0] + ' '; e.preventDefault(); }
    });
  }
  function toggleTerm(force) {
    if (!term) buildTerm();
    const open = force === undefined ? !term.classList.contains('open') : force;
    term.classList.toggle('open', open); if (open) setTimeout(() => $('input', term).focus(), 60);
  }
  document.addEventListener('keydown', e => {
    const t = e.target; const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
    if ((e.key === '`' || e.key === '~') && !typing && !e.ctrlKey && !e.metaKey) { e.preventDefault(); toggleTerm(); }
  });

  /* ------------------------------------------------------------------ boot */
  function init() {
    pointerFx(); if (bg.on) setBg(true, true); bootSeq();
    (window.v2ExtraCommands = window.v2ExtraCommands || []).push(() => [
      { g: '✦', grp: 'View', name: 'Toggle constellation background', run: () => setBg(!bg.on) },
      { g: '❯', grp: 'View', name: 'Open console', hint: '`', run: () => toggleTerm(true) }
    ]);
  }
  window.spac3FX = { setBg, toggleTerm };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
