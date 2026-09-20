/* Spac3-Gh0st v2 UI layer: vitals strip, command palette, toasts, card folding,
   theme cycling, connection status, export. Purely additive: it reads the
   globals app.js already maintains (lastStatus, activeTab, showTab, refresh...)
   and never replaces them. */
(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };
  var status = function () { try { return typeof lastStatus !== 'undefined' ? lastStatus : null; } catch (e) { return null; } };
  var call = function (name) {
    var args = Array.prototype.slice.call(arguments, 1);
    try { if (typeof window[name] === 'function') return window[name].apply(null, args); } catch (e) { toast('Action failed', String(e && e.message || e), 'bad'); }
  };
  var esc = function (s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };

  /* ------------------------------------------------------------------ toasts */
  var toastHost;
  function toast(title, text, kind, ms) {
    if (!toastHost) { toastHost = document.createElement('div'); toastHost.className = 'v2-toasts'; toastHost.setAttribute('aria-live', 'polite'); document.body.appendChild(toastHost); }
    var colors = { ok: 'var(--green)', warn: 'var(--yellow)', bad: 'var(--red)', info: 'var(--cyan)' };
    var icons = { ok: '✓', warn: '!', bad: '✕', info: 'i' };
    kind = colors[kind] ? kind : 'info';
    var el = document.createElement('div');
    el.className = 'v2-toast'; el.style.setProperty('--tc', colors[kind]);
    el.innerHTML = '<div class="ic">' + icons[kind] + '</div><div><b>' + esc(title) + '</b><span>' + esc(text || '') + '</span></div><button class="x" aria-label="Dismiss">×</button>';
    var close = function () { el.classList.add('out'); setTimeout(function () { el.remove(); }, 300); };
    $('.x', el).onclick = close;
    toastHost.appendChild(el);
    while (toastHost.children.length > 4) toastHost.firstChild.remove();
    setTimeout(close, ms || 5200);
  }
  window.v2Toast = toast;

  /* ------------------------------------------------------------------ themes */
  var THEMES = ['default', 'aurora', 'synthwave', 'glacier', 'mono', 'purple', 'blue', 'orange', 'red', 'yellow'];
  function currentTheme() { return document.body.dataset.theme || 'default'; }
  function setTheme(t) {
    if (typeof applyTheme === 'function') applyTheme(t); else document.body.dataset.theme = t;
    store.set('spac3Theme', t);
    var sel = $('#themeSelect'); if (sel) sel.value = t;
  }
  function cycleTheme(dir) {
    var i = THEMES.indexOf(currentTheme()); if (i < 0) i = 0;
    var t = THEMES[(i + (dir || 1) + THEMES.length) % THEMES.length];
    setTheme(t); toast('Theme', t, 'info', 1800);
  }
  function extendThemeSelect() {
    var sel = $('#themeSelect'); if (!sel) return;
    THEMES.forEach(function (t) {
      if (!$$('option', sel).some(function (o) { return o.value === t; })) {
        var o = document.createElement('option'); o.value = t; o.textContent = t.charAt(0).toUpperCase() + t.slice(1); sel.appendChild(o);
      }
    });
    sel.value = currentTheme();
  }

  /* ------------------------------------------------------------------ toggles */
  function flag(cls, key, label) {
    var on = !document.body.classList.contains(cls);
    document.body.classList.toggle(cls, on); store.set(key, on ? '1' : '0');
    toast(label, on ? 'on' : 'off', 'info', 1600);
  }
  function fullscreen() {
    try { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); } catch (e) { toast('Fullscreen', 'not available here', 'warn'); }
  }

  /* ------------------------------------------------------------------ vitals */
  var HIST = {}; var HIST_MAX = 40;
  var TILES = [
    { k: 'cpu', label: 'CPU', unit: '%', pct: true, get: function (s) { return num(s.system && s.system.cpu_live && s.system.cpu_live.percent); }, sub: function (s) { var c = s.system && s.system.cpu_live; return c ? (c.cores ? c.cores + ' cores' : '') + (c.freq_mhz ? ' · ' + Math.round(c.freq_mhz) + ' MHz' : '') : ''; }, warn: 70, bad: 90 },
    { k: 'ram', label: 'Memory', unit: '%', pct: true, get: function (s) { return num(s.system && s.system.memory && s.system.memory.percent); }, sub: function (s) { var m = s.system && s.system.memory; return m && m.total_mb ? m.used_mb + ' / ' + m.total_mb + ' MB' : ''; }, warn: 75, bad: 90 },
    { k: 'disk', label: 'Disk', unit: '%', pct: true, get: function (s) { return diskPct(s); }, sub: function (s) { var d = s.system && s.system.disk_all && s.system.disk_all[0]; return d ? d.mount + ' · ' + d.avail + ' free' : ''; }, warn: 80, bad: 93 },
    { k: 'temp', label: 'CPU Temp', unit: '°C', get: function (s) { return num(s.system && s.system.cpu_temp_c); }, max: 90, sub: function (s) { var f = s.system && s.system.cpu_temp_f; return f != null ? f + ' °F' : 'sensor unavailable'; }, warn: 65, bad: 75 },
    { k: 'net', label: 'Network', text: function (s) { var n = s.system && s.system.net_io; if (!n || !n.available) return null; return rate(n.rx_bps) + '↓ ' + rate(n.tx_bps) + '↑'; }, get: function (s) { var n = s.system && s.system.net_io; return n && n.available ? num(n.rx_bps) : null; }, sub: function (s) { return (s.system && s.system.ips && s.system.ips[0]) || ''; } },
    { k: 'uptime', label: 'Uptime', text: function (s) { return s.system && s.system.uptime_s != null ? dur(s.system.uptime_s) : null; }, sub: function (s) { var h = s.system && s.system.hostname; var p = s.system && s.system.platform; return (h || '') + (p && p.os ? ' · ' + p.os : ''); } },
    { k: 'signals', label: 'Signals', text: function (s) { return cnt(s.wifi, 'networks') + ' / ' + cnt(s.bluetooth, 'devices') + ' / ' + cnt(s.lan, 'devices'); }, sub: function () { return 'Wi-Fi / BT / LAN'; } },
    { k: 'alert', label: 'Alert Level', text: function (s) { return s.alert && s.alert.level ? s.alert.level : null; }, sub: function (s) { return s.alert ? 'score ' + (s.alert.score != null ? s.alert.score : 0) : ''; }, state: function (s) { var l = s.alert && s.alert.level; return !l ? 'na' : (l === 'GREEN' ? 'ok' : (l === 'YELLOW' || l === 'ORANGE' ? 'warn' : 'bad')); } }
  ];
  function num(v) { if (v === null || v === undefined || v === '') return null; v = Number(v); return isFinite(v) ? v : null; }
  function cnt(o, k) { return o && o[k] ? o[k].length : 0; }
  function diskPct(s) {
    var d = s.system && s.system.disk_all && s.system.disk_all[0];
    var m = d && /(\d+)%/.exec(d.use_percent || '');
    if (m) return +m[1];
    m = /(\d+)%/.exec((s.system && s.system.disk_root) || ''); return m ? +m[1] : null;
  }
  function rate(b) { b = Number(b) || 0; if (b > 1048576) return (b / 1048576).toFixed(1) + 'M'; if (b > 1024) return (b / 1024).toFixed(0) + 'K'; return Math.round(b) + 'B'; }
  function dur(sec) { var d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60); return d ? d + 'd ' + h + 'h' : (h ? h + 'h ' + m + 'm' : m + 'm'); }

  function spark(vals) {
    if (vals.length < 2) return '';
    var w = 64, h = 26, lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    if (hi - lo < 1e-6) { hi = lo + 1; }
    var pts = vals.map(function (v, i) { return [(i / (vals.length - 1) * w).toFixed(1), (h - 2 - (v - lo) / (hi - lo) * (h - 4)).toFixed(1)]; });
    var line = pts.map(function (p) { return p.join(','); }).join(' ');
    return '<svg class="spark" viewBox="0 0 ' + w + ' ' + h + '" aria-hidden="true"><path d="M0,' + h + ' L' + line.replace(/ /g, ' L') + ' L' + w + ',' + h + ' Z"/><polyline points="' + line + '"/></svg>';
  }

  var vitals;
  function buildVitals() {
    var nav = $('nav.tabs'); if (!nav) return;
    vitals = document.createElement('section'); vitals.className = 'v2-vitals'; vitals.setAttribute('aria-label', 'Live vitals');
    vitals.innerHTML = TILES.map(function (t) { return '<div class="v2-tile" data-k="' + t.k + '" data-state="na" tabindex="0"><span class="lbl">' + t.label + '</span><b class="val">--</b><span class="sub"></span><i class="bar"></i></div>'; }).join('');
    nav.parentNode.insertBefore(vitals, nav.nextSibling);
  }
  var lastRendered = null;
  function renderVitals() {
    var s = status(); if (!s || !vitals || s === lastRendered) return; lastRendered = s;
    TILES.forEach(function (t) {
      var el = $('[data-k="' + t.k + '"]', vitals); if (!el) return;
      var v = t.get ? t.get(s) : null;
      var txt = t.text ? t.text(s) : null;
      if (v !== null && t.get) { (HIST[t.k] = HIST[t.k] || []).push(v); if (HIST[t.k].length > HIST_MAX) HIST[t.k].shift(); }
      var state = 'na', valHtml = '--', pct = 0;
      if (t.state) { state = t.state(s); valHtml = txt != null ? esc(txt) : '--'; }
      else if (txt != null) { state = 'ok'; valHtml = esc(txt); }
      else if (v !== null) {
        valHtml = (Math.round(v * 10) / 10) + '<small>' + t.unit + '</small>';
        state = t.bad != null && v >= t.bad ? 'bad' : (t.warn != null && v >= t.warn ? 'warn' : 'ok');
        pct = t.pct ? v : (t.max ? Math.min(100, v / t.max * 100) : 0);
      }
      el.dataset.state = state;
      el.style.setProperty('--p', Math.max(0, Math.min(100, pct)) + '%');
      $('.val', el).innerHTML = valHtml;
      $('.sub', el).textContent = (t.sub && t.sub(s)) || '';
      var old = $('.spark', el); if (old) old.remove();
      var sp = spark(HIST[t.k] || []); if (sp && t.get) el.insertAdjacentHTML('afterbegin', sp);
    });
  }

  /* ------------------------------------------------------------------ connection pill + clock */
  var pill, dateEl, lastOk = Date.now(), failing = 0;
  function buildHud() {
    var clock = $('#clock'); var header = $('header'); if (!clock || !header) return;
    var hud = document.createElement('div'); hud.className = 'v2-hud';
    pill = document.createElement('span'); pill.className = 'v2-pill'; pill.dataset.state = 'stale';
    pill.innerHTML = '<i class="dot"></i><span>CONNECTING</span>';
    var pal = btn('⌘ Search<kbd>Ctrl K</kbd>', 'Command palette (Ctrl/Cmd+K)', openPalette, 'v2-hide-sm');
    var th = btn('◐ Theme', 'Cycle theme (T)', function () { cycleTheme(1); });
    var fs = btn('⤢', 'Fullscreen (F)', fullscreen, 'v2-hide-sm');
    var box = document.createElement('div'); box.className = 'v2-clockbox';
    clock.parentNode.insertBefore(box, clock); box.appendChild(clock);
    dateEl = document.createElement('span'); dateEl.className = 'v2-date'; box.appendChild(dateEl);
    hud.appendChild(pill); hud.appendChild(pal); hud.appendChild(th); hud.appendChild(fs); hud.appendChild(box);
    header.appendChild(hud);
    tickDate();
  }
  function btn(html, title, fn, extra) {
    var b = document.createElement('button'); b.className = 'v2-iconbtn ' + (extra || ''); b.innerHTML = html; b.title = title; b.onclick = fn; b.type = 'button'; return b;
  }
  function tickDate() { if (dateEl) dateEl.textContent = new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }).toUpperCase(); }
  function setConn(state, label) { if (!pill) return; pill.dataset.state = state; $('span', pill).textContent = label; }
  function heartbeat() {
    var t0 = performance.now();
    fetch('/api/health', { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (h) {
      failing = 0; lastOk = Date.now();
      var ms = Math.round(performance.now() - t0);
      var s = status(); var age = s && s.cache_age_s;
      setConn(age != null && age > 90 ? 'stale' : 'live', 'LIVE · ' + ms + ' ms');
      var f = $('.v2-ver'); if (f) f.textContent = 'v' + h.version + ' · ' + h.plugins.loaded + '/' + h.plugins.total + ' plugins · server up ' + dur(h.uptime_s);
    }).catch(function () {
      failing++;
      setConn(failing > 2 ? 'down' : 'stale', failing > 2 ? 'OFFLINE' : 'RETRYING');
      if (failing === 3) toast('Connection lost', 'Dashboard server is not responding. Retrying...', 'bad');
    });
  }

  /* ------------------------------------------------------------------ event -> toast bridge */
  var seenTs = null, lastAlert = null;
  var KINDS = { alert: ['Alert', 'bad'], service: ['Service', 'warn'], thermal: ['Thermal', 'warn'], gps: ['GPS', 'info'], vpn: ['VPN', 'info'], vision: ['Vision', 'info'], boot: ['Boot', 'ok'], scan: ['Scan', 'info'] };
  function pollEvents() {
    var s = status(); if (!s) return;
    var evs = s.events || [];
    if (seenTs === null) { seenTs = evs.length ? evs[0].ts : 0; lastAlert = s.alert && s.alert.level; return; }
    evs.slice().reverse().forEach(function (e) {
      if (e.ts > seenTs && KINDS[e.kind]) toast(KINDS[e.kind][0], e.text, KINDS[e.kind][1]);
    });
    if (evs.length) seenTs = Math.max(seenTs, evs[0].ts);
    var lvl = s.alert && s.alert.level;
    if (lvl && lastAlert && lvl !== lastAlert) toast('Alert level ' + lvl, (s.alert.reasons || []).slice(0, 2).join(' · ') || 'status changed', lvl === 'GREEN' ? 'ok' : 'warn');
    lastAlert = lvl || lastAlert;
  }

  /* ------------------------------------------------------------------ card folding */
  function cardKey(card) { var h = $('h2', card); return (card.closest('.tab-panel') || {}).id + ':' + (h ? h.textContent.trim() : ''); }
  function foldState() { try { return JSON.parse(store.get('v2Folded', '{}')); } catch (e) { return {}; } }
  function saveFold(o) { store.set('v2Folded', JSON.stringify(o)); }
  function decorateCards() {
    var folded = foldState();
    $$('.card').forEach(function (card) {
      var h = card.querySelector(':scope > h2'); if (!h || $('.v2-fold', h) || card.classList.contains('page-hero')) return;
      var b = document.createElement('button'); b.type = 'button'; b.className = 'v2-fold'; b.textContent = '⌄'; b.title = 'Collapse / expand';
      b.setAttribute('aria-label', 'Collapse or expand ' + h.textContent.trim());
      b.onclick = function (ev) { ev.stopPropagation(); var f = foldState(); var on = card.classList.toggle('v2-collapsed'); if (on) f[cardKey(card)] = 1; else delete f[cardKey(card)]; saveFold(f); };
      h.appendChild(b);
      if (folded[cardKey(card)]) card.classList.add('v2-collapsed');
    });
  }
  function foldAll(on) {
    var f = {};
    $$('.card').forEach(function (c) { if ($(':scope > h2 .v2-fold', c)) { c.classList.toggle('v2-collapsed', on); if (on) f[cardKey(c)] = 1; } });
    saveFold(f); toast(on ? 'Collapsed all cards' : 'Expanded all cards', '', 'info', 1500);
  }

  /* ------------------------------------------------------------------ export */
  function exportStatus() {
    var s = status(); if (!s) { toast('Export', 'No status loaded yet', 'warn'); return; }
    var copy = JSON.parse(JSON.stringify(s));
    // never export saved Wi-Fi secrets or config that may hold credentials
    delete copy.config; if (copy.known_wifi) delete copy.known_wifi;
    var blob = new Blob([JSON.stringify(copy, null, 2)], { type: 'application/json' });
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'spac3ghost-status-' + new Date().toISOString().replace(/[:.]/g, '-') + '.json'; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    toast('Exported', 'Status snapshot saved (config omitted)', 'ok');
  }

  /* ------------------------------------------------------------------ command palette */
  var TABS = [['dash', 'Dashboard', '◉'], ['deck', 'Deck', '◈'], ['systems', 'Systems', '⚙'], ['signals', 'Signals', '⌁'], ['lab', 'Lab', '⚗'], ['externals', 'Externals', '↗'], ['settings', 'Settings', '☰']];
  function goTab(t) { call('showTab', t); }
  function commands() {
    var list = [];
    TABS.forEach(function (t, i) { list.push({ g: t[2], grp: 'Go to', name: t[1], hint: String(i + 1), run: function () { goTab(t[0]); } }); });
    list.push(
      { g: '↻', grp: 'Actions', name: 'Refresh now', hint: 'R', run: function () { call('refresh'); toast('Refreshing', '', 'info', 1200); } },
      { g: '⌁', grp: 'Actions', name: 'Scan LAN', run: function () { call('scan', 'lan'); toast('LAN scan', 'started', 'info'); } },
      { g: '⌁', grp: 'Actions', name: 'Scan Bluetooth', run: function () { call('scan', 'bluetooth'); toast('Bluetooth scan', 'started', 'info'); } },
      { g: '⌁', grp: 'Actions', name: 'Scan Wi-Fi', run: function () { call('scan', 'wifi'); toast('Wi-Fi scan', 'started', 'info'); } },
      { g: '♪', grp: 'Actions', name: 'Toggle sound', run: function () { call('toggleSound'); } },
      { g: '⇩', grp: 'Actions', name: 'Export status snapshot (JSON)', run: exportStatus },
      { g: '⧉', grp: 'Actions', name: 'Copy dashboard URL', run: function () { try { navigator.clipboard.writeText(location.href); toast('Copied', location.href, 'ok', 2200); } catch (e) { toast('Copy failed', '', 'warn'); } } },
      { g: '◐', grp: 'View', name: 'Next theme', hint: 'T', run: function () { cycleTheme(1); } },
      { g: '◑', grp: 'View', name: 'Previous theme', hint: 'Shift T', run: function () { cycleTheme(-1); } },
      { g: '▤', grp: 'View', name: 'Toggle CRT scanlines', run: function () { flag('v2-crt', 'v2Crt', 'CRT scanlines'); } },
      { g: '▥', grp: 'View', name: 'Toggle compact density', run: function () { flag('v2-compact', 'v2Compact', 'Compact density'); } },
      { g: '⤢', grp: 'View', name: 'Toggle fullscreen', hint: 'F', run: fullscreen },
      { g: '⌃', grp: 'View', name: 'Collapse all cards', run: function () { foldAll(true); } },
      { g: '⌄', grp: 'View', name: 'Expand all cards', run: function () { foldAll(false); } },
      { g: '?', grp: 'Help', name: 'Keyboard shortcuts', hint: '?', run: showHelp }
    );
    (window.v2ExtraCommands || []).forEach(function (fn) { try { fn().forEach(function (c) { list.push(c); }); } catch (e) { /* optional */ } });
    THEMES.forEach(function (t) { list.push({ g: '●', grp: 'Themes', name: 'Theme: ' + t, run: function () { setTheme(t); toast('Theme', t, 'info', 1500); } }); });
    $$('.tab-panel').forEach(function (p) {
      $$('.card > h2', p).forEach(function (h) {
        var label = h.childNodes[0] ? h.childNodes[0].textContent.trim() : h.textContent.trim();
        if (label) list.push({ g: '§', grp: 'Jump to card', name: label, hint: p.id.replace('tab-', ''), run: function () { jumpToCard(p, h.parentElement); } });
      });
    });
    return list;
  }
  function jumpToCard(panel, card) {
    goTab(panel.id.replace('tab-', ''));
    setTimeout(function () { card.classList.remove('v2-collapsed'); card.scrollIntoView({ behavior: 'smooth', block: 'center' }); card.classList.remove('v2-flash'); void card.offsetWidth; card.classList.add('v2-flash'); }, 120);
  }
  function score(q, s) {
    q = q.toLowerCase(); s = s.toLowerCase(); if (!q) return 1;
    var i = s.indexOf(q); if (i >= 0) return 100 - i;
    var qi = 0, sc = 0, last = -2;
    for (var k = 0; k < s.length && qi < q.length; k++) { if (s[k] === q[qi]) { sc += (k === last + 1 ? 3 : 1); last = k; qi++; } }
    return qi === q.length ? sc : 0;
  }
  var back, input, listEl, items = [], sel = 0;
  function buildPalette() {
    back = document.createElement('div'); back.className = 'v2-cmd-back'; back.setAttribute('role', 'dialog'); back.setAttribute('aria-modal', 'true'); back.setAttribute('aria-label', 'Command palette');
    back.innerHTML = '<div class="v2-cmd"><input type="text" placeholder="Type a command, tab, or card name..." aria-label="Search commands" autocomplete="off" spellcheck="false"><div class="v2-cmd-list" role="listbox"></div><div class="v2-cmd-foot"><span><kbd>↑↓</kbd>navigate</span><span><kbd>Enter</kbd>run</span><span><kbd>Esc</kbd>close</span></div></div>';
    document.body.appendChild(back);
    input = $('input', back); listEl = $('.v2-cmd-list', back);
    back.addEventListener('mousedown', function (e) { if (e.target === back) closePalette(); });
    input.addEventListener('input', function () { sel = 0; renderList(); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, items.length - 1); paintSel(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); paintSel(); e.preventDefault(); }
      else if (e.key === 'Enter') { runItem(sel); e.preventDefault(); }
      else if (e.key === 'Escape') { closePalette(); e.preventDefault(); }
    });
  }
  function renderList() {
    var q = input.value.trim(), all = commands();
    items = all.map(function (c) { return { c: c, s: score(q, c.name + ' ' + c.grp) }; }).filter(function (x) { return x.s > 0; });
    if (q) items.sort(function (a, b) { return b.s - a.s; });
    items = items.slice(0, 60).map(function (x) { return x.c; });
    if (!items.length) { listEl.innerHTML = '<div class="v2-cmd-empty">No matches for “' + esc(q) + '”</div>'; return; }
    var html = '', grp = '';
    items.forEach(function (c, i) {
      if (!q && c.grp !== grp) { grp = c.grp; html += '<div class="v2-cmd-group">' + esc(grp) + '</div>'; }
      html += '<button type="button" class="v2-cmd-item" role="option" data-i="' + i + '"><span class="g">' + esc(c.g) + '</span><span>' + esc(c.name) + '</span>' + (c.hint ? '<span class="h">' + esc(c.hint) + '</span>' : '') + '</button>';
    });
    listEl.innerHTML = html;
    $$('.v2-cmd-item', listEl).forEach(function (b) { b.onclick = function () { runItem(+b.dataset.i); }; b.onmousemove = function () { sel = +b.dataset.i; paintSel(true); }; });
    paintSel();
  }
  function paintSel(noScroll) {
    $$('.v2-cmd-item', listEl).forEach(function (b) { var on = +b.dataset.i === sel; b.classList.toggle('sel', on); b.setAttribute('aria-selected', on); if (on && !noScroll) b.scrollIntoView({ block: 'nearest' }); });
  }
  function runItem(i) { var c = items[i]; if (!c) return; closePalette(); setTimeout(function () { c.run(); }, 30); }
  function openPalette() { if (!back) buildPalette(); back.classList.add('open'); input.value = ''; sel = 0; renderList(); setTimeout(function () { input.focus(); }, 10); }
  function closePalette() { if (back) back.classList.remove('open'); }
  function showHelp() {
    var h = document.createElement('div'); h.className = 'v2-cmd-back open'; h.setAttribute('role', 'dialog'); h.setAttribute('aria-label', 'Keyboard shortcuts');
    h.innerHTML = '<div class="v2-cmd"><div class="v2-help"><h3>Keyboard shortcuts</h3>' +
      '<div><kbd>Ctrl/\u2318 K</kbd> or <kbd>/</kbd> command palette</div><div><kbd>1</kbd>\u2013<kbd>7</kbd> switch tabs</div>' +
      '<div><kbd>R</kbd> refresh</div><div><kbd>T</kbd> / <kbd>Shift T</kbd> next / previous theme</div><div><kbd>F</kbd> fullscreen</div><div><kbd>?</kbd> this help</div><div><kbd>Esc</kbd> close</div></div></div>';
    var close = function (e) { if (e.type === 'keydown' && e.key !== 'Escape') return; h.remove(); document.removeEventListener('keydown', close); };
    h.addEventListener('mousedown', function (e) { if (e.target === h) close(e); });
    document.addEventListener('keydown', close);
    document.body.appendChild(h);
  }

  /* ------------------------------------------------------------------ keyboard */
  function typing(e) { var t = e.target; return t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable); }
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); return; }
    if (typing(e) || e.ctrlKey || e.metaKey || e.altKey) return;
    if (back && back.classList.contains('open')) return;
    var k = e.key;
    if (k === '/') { e.preventDefault(); openPalette(); }
    else if (k >= '1' && k <= '7') goTab(TABS[+k - 1][0]);
    else if (k === 'r' || k === 'R') { call('refresh'); toast('Refreshing', '', 'info', 1000); }
    else if (k === 't') cycleTheme(1);
    else if (k === 'T') cycleTheme(-1);
    else if (k === 'f' || k === 'F') fullscreen();
    else if (k === '?') showHelp();
  });

  /* ------------------------------------------------------------------ boot */
  function init() {
    if (store.get('v2Crt', '0') === '1') document.body.classList.add('v2-crt');
    if (store.get('v2Compact', '0') === '1') document.body.classList.add('v2-compact');
    var glyphs = { dash: '◉', deck: '◈', systems: '⚙', signals: '⌁', lab: '⚗', externals: '↗', settings: '☰' };
    $$('.tab-button').forEach(function (b) { b.dataset.glyph = glyphs[b.dataset.tab] || '•'; });
    var logo = $('header .logo'); if (logo) { var ver = document.createElement('span'); ver.className = 'v2-ver'; logo.parentNode.appendChild(ver); }
    buildHud(); buildVitals(); extendThemeSelect(); decorateCards();
    var s0 = store.get('spac3Theme', null); if (s0 && THEMES.indexOf(s0) >= 0) setTheme(s0);
    heartbeat(); setInterval(heartbeat, 10000);
    setInterval(function () { renderVitals(); pollEvents(); }, 1500);
    setInterval(tickDate, 60000);
    // some cards are rendered lazily by app.js; keep folding controls in sync
    setInterval(decorateCards, 4000);
    // first load: the server answers with a "warming" placeholder until its slow collectors finish.
    // app.js only re-polls every 15 s, so nudge it until real data arrives.
    var warm = setInterval(function () {
      var s = status();
      if (s && s.cache_state !== 'warming' && s.system && Object.keys(s.system).length) { clearInterval(warm); return; }
      if (typeof window.refresh === 'function') window.refresh();
    }, 2500);
    setTimeout(function () { clearInterval(warm); }, 60000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
