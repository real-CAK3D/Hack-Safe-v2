/* Spac3-Gh0st weather engine (canvas).
   Replaces the old CSS-only sky with a layered simulation: physically-tinted sky
   gradients from sun altitude, volumetric sprite clouds with parallax, depth-sorted
   wind-slanted rain with ground splashes, swaying snow, forked lightning with sky
   flash, drifting fog, real moon phase, twinkling stars, hills and pines.
   It reads the same weather data the dashboard already has (lastStatus) and
   re-attaches itself whenever app.js re-renders the Weather Ops card. */
(function () {
  'use strict';

  var TAU = Math.PI * 2;
  var REDUCED = false;
  try { REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { /* older browsers */ }

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function mix(c1, c2, t) { return [lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t)]; }
  function rgb(c, a) { return 'rgba(' + (c[0] | 0) + ',' + (c[1] | 0) + ',' + (c[2] | 0) + ',' + (a === undefined ? 1 : a) + ')'; }
  // tiny deterministic PRNG so scenery (hills, stars, cloud shapes) is stable across re-renders
  function rng(seed) { var s = seed >>> 0; return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }

  /* ------------------------------------------------------------- weather model */
  var PRESETS = {
    'Clear day':        { kind: 'clear', cloud: 0.12, intensity: 0, wind: 6, tod: 'day' },
    'Partly cloudy':    { kind: 'cloud', cloud: 0.45, intensity: 0, wind: 9, tod: 'day' },
    'Overcast':         { kind: 'cloud', cloud: 0.92, intensity: 0, wind: 8, tod: 'day' },
    'Light rain':       { kind: 'rain',  cloud: 0.85, intensity: 0.5, wind: 7, tod: 'day' },
    'Heavy rain':       { kind: 'rain',  cloud: 0.95, intensity: 1.8, wind: 16, tod: 'day' },
    'Thunderstorm':     { kind: 'storm', cloud: 1, intensity: 2.2, wind: 24, tod: 'dusk' },
    'Snow':             { kind: 'snow',  cloud: 0.8, intensity: 1, wind: 5, tod: 'day' },
    'Blizzard':         { kind: 'snow',  cloud: 0.95, intensity: 2.4, wind: 30, tod: 'day' },
    'Fog':              { kind: 'fog',   cloud: 0.55, intensity: 0, fog: 0.85, wind: 3, tod: 'day' },
    'Clear night':      { kind: 'clear', cloud: 0.1, intensity: 0, wind: 4, tod: 'night' },
    'Rainy night':      { kind: 'rain',  cloud: 0.9, intensity: 1.1, wind: 10, tod: 'night' },
    'Golden hour':      { kind: 'cloud', cloud: 0.3, intensity: 0, wind: 6, tod: 'dawn' }
  };
  var override = null;

  function liveWeather() {
    try { return (typeof lastStatus !== 'undefined' && lastStatus && lastStatus.sensors && lastStatus.sensors.weather) || {}; } catch (e) { return {}; }
  }
  function clockMinutes(str) {
    var m = String(str || '').trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i); if (!m) return null;
    var h = +m[1], mi = +m[2], ap = (m[3] || '').toUpperCase();
    if (ap === 'PM' && h < 12) h += 12; if (ap === 'AM' && h === 12) h = 0; return h * 60 + mi;
  }

  /** Turn live sensor data (or a preview preset) into the numbers the renderer needs. */
  function deriveTarget() {
    var wx = liveWeather(), P = {};
    var src = override;
    var sum = String(wx.summary || '').toLowerCase();
    if (src) {
      P.kind = src.kind; P.cloud = src.cloud; P.intensity = src.intensity; P.fog = src.fog || (src.kind === 'fog' ? .8 : 0); P.wind = src.wind;
      P.label = src.label;
    } else {
      var storm = /storm|thunder/.test(sum), rain = storm || /rain|shower|drizzle/.test(sum), snow = /snow|sleet|flurr|blizzard/.test(sum);
      var fog = /fog|mist|haze|smoke/.test(sum), cloudy = /cloud|overcast/.test(sum), clear = /clear|sun|fair/.test(sum);
      P.kind = storm ? 'storm' : rain ? 'rain' : snow ? 'snow' : fog ? 'fog' : cloudy ? 'cloud' : 'clear';
      var partly = /partly|few|scattered|mostly clear/.test(sum);
      P.cloud = storm ? 1 : rain ? .88 : snow ? .84 : fog ? .55 : cloudy ? (partly ? .45 : /overcast|mostly cloudy|broken/.test(sum) ? .92 : .68) : clear ? .1 : .3;
      var inten = /heavy|violent|torrential/.test(sum) ? 1.8 : /light|drizzle|few|slight/.test(sum) ? .5 : 1;
      P.intensity = storm ? Math.max(inten, 1.6) * 1.2 : (rain || snow) ? inten : 0;
      P.fog = fog ? .8 : 0;
      P.wind = Number(wx.windMph) || 0;
      P.label = wx.summary || 'weather n/a';
      if (!wx.summary) { P.kind = 'clear'; P.cloud = .15; }
    }
    // sun / moon position
    var now = new Date(), mins = now.getHours() * 60 + now.getMinutes();
    var sr = clockMinutes(wx.sunrise), ss = clockMinutes(wx.sunset);
    if (sr == null || ss == null || ss <= sr) { sr = 390; ss = 1170; }
    var tod = src && src.tod;
    var isDay, p, nightP;
    if (tod === 'day') { isDay = true; p = .5; }
    else if (tod === 'dawn') { isDay = true; p = .04; }
    else if (tod === 'dusk') { isDay = true; p = .965; }
    else if (tod === 'night') { isDay = false; nightP = .5; }
    else {
      isDay = mins >= sr && mins < ss;
      if (isDay) p = (mins - sr) / (ss - sr);
      else { var len = 1440 - (ss - sr); var since = mins >= ss ? mins - ss : mins + 1440 - ss; nightP = since / len; }
    }
    if (isDay) { P.alt = Math.sin(p * Math.PI); P.p = p; }
    else { P.alt = -clamp(Math.min(nightP, 1 - nightP) * 9, 0, 1); P.p = nightP; }
    P.isDay = isDay;
    P.temp = Number(wx.tempF);
    P.label = (P.label || '') ;
    return P;
  }

  /* ------------------------------------------------------------- engine state */
  var E = {
    canvas: null, ctx: null, w: 0, h: 0, dpr: 1, raf: 0, last: 0, time: 0,
    cur: { cloud: .2, fog: 0, wind: 4, alt: .8, intensity: 0, rainAmt: 0, snowAmt: 0, storm: 0 },
    tgt: null, kind: 'clear', isDay: true, p: .5, hills: null, stars: null, sprites: null, spriteKey: '',
    clouds: [], rain: [], snow: [], splashes: [], lightning: { next: 4, flash: 0, bolt: null, second: 0 },
    shoot: null, nextShoot: 12, tag: null, lastDerive: 0, snap: true
  };
  var RAIN_MAX = 420, SNOW_MAX = 260;

  function seedParticles() {
    var r = rng(7);
    E.rain = []; for (var i = 0; i < RAIN_MAX; i++) E.rain.push({ x: r(), y: r(), z: .25 + r() * .75, gy: r() });
    E.snow = []; for (i = 0; i < SNOW_MAX; i++) E.snow.push({ x: r(), y: r(), z: .2 + r() * .8, ph: r() * TAU, sp: .6 + r() * .8 });
  }
  seedParticles();

  /* ------------------------------------------------------------- scenery generation */
  function buildScenery() {
    var w = E.w, h = E.h, r = rng(42);
    // hills: three parallax layers from sums of sines
    E.hills = [];
    for (var L = 0; L < 3; L++) {
      var pts = [], a1 = r() * 10, a2 = r() * 10, a3 = r() * 10;
      var horizon = [h * .74, h * .80, h * .88][L];
      var amp = [h * .085, h * .06, h * .04][L];
      for (var x = 0; x <= w + 8; x += 6) {
        var nx = x / w;
        var y = horizon - amp * (.55 + .28 * Math.sin(nx * (3.1 + L) + a1) + .17 * Math.sin(nx * (8.3 + 2 * L) + a2) + .08 * Math.sin(nx * 21 + a3));
        pts.push([x, y]);
      }
      E.hills.push({ pts: pts, L: L });
    }
    // pines on the middle hill
    E.trees = [];
    var mid = E.hills[1].pts;
    for (var i = 0; i < mid.length; i += 3 + Math.floor(r() * 3)) {
      if (r() < .78) E.trees.push({ x: mid[i][0], y: mid[i][1] + 2, s: (.7 + r() * .8) * clamp(h / 230, .55, 1.25), ph: r() * TAU });
    }
    E.stars = [];
    for (i = 0; i < 90; i++) E.stars.push({ x: r() * w, y: r() * h * .62, r: .4 + r() * 1.1, ph: r() * TAU, sp: .8 + r() * 2 });
    // clouds re-placed on resize
    E.clouds = [];
    for (i = 0; i < 14; i++) E.clouds.push({ x: r(), y: .04 + r() * .38, s: .55 + r() * .9, sp: .5 + r(), spr: Math.floor(r() * 6), layer: r() });
  }

  /* cloud sprites: soft radial puffs, lit on top / shaded below, tinted by ambient light */
  function ambientKey(alt, dark) { return (alt > .35 ? 'd' : alt > .02 ? 'g' : alt > -.25 ? 't' : 'n') + Math.round(dark * 4); }
  function buildSprites(alt, dark) {
    var lit, shade;
    if (alt > .35) { lit = [255, 255, 255]; shade = [172, 188, 210]; }
    else if (alt > .02) { lit = [255, 208, 165]; shade = [150, 118, 140]; }
    else if (alt > -.25) { lit = [120, 110, 150]; shade = [42, 44, 78]; }
    else { lit = [78, 92, 132]; shade = [20, 26, 46]; }
    var stormLit = [104, 112, 126], stormShade = [34, 38, 48];
    lit = mix(lit, stormLit, dark * .85); shade = mix(shade, stormShade, dark * .9);
    var out = [], r = rng(99);
    for (var s = 0; s < 6; s++) {
      var W = 340, H = 150, c = document.createElement('canvas'); c.width = W; c.height = H; var g = c.getContext('2d');
      var puffs = 9 + Math.floor(r() * 6), items = [];
      for (var i = 0; i < puffs; i++) {
        var t = i / (puffs - 1), px = 40 + t * (W - 80) + (r() - .5) * 30;
        var bump = Math.sin(t * Math.PI); var rad = 24 + bump * 30 + r() * 16;
        items.push({ x: px, y: H * .62 - bump * 26 - r() * 14, r: rad });
      }
      function puff(p, col, dy, a) {
        var gr = g.createRadialGradient(p.x, p.y + dy, p.r * .05, p.x, p.y + dy, p.r);
        gr.addColorStop(0, rgb(col, a)); gr.addColorStop(.62, rgb(col, a * .9)); gr.addColorStop(.88, rgb(col, a * .35)); gr.addColorStop(1, rgb(col, 0));
        g.fillStyle = gr; g.beginPath(); g.arc(p.x, p.y + dy, p.r, 0, TAU); g.fill();
      }
      items.forEach(function (p) { puff(p, shade, 10, 1); });
      items.forEach(function (p) { puff({ x: p.x, y: p.y, r: p.r * .92 }, mix(shade, lit, .5), 1, 1); });
      items.forEach(function (p) { puff({ x: p.x - p.r * .12, y: p.y, r: p.r * .72 }, lit, -p.r * .22, .95); });
      out.push(c);
    }
    E.sprites = out;
  }

  /* ------------------------------------------------------------- drawing */
  function skyColors(alt, cloud, storm) {
    var top, bot;
    var dayT = [44, 122, 212], dayB = [150, 205, 245], twT = [62, 70, 140], twB = [246, 152, 94], nT = [5, 9, 26], nB = [17, 27, 60];
    if (alt >= 0) { var t = clamp(alt / .38, 0, 1); top = mix(twT, dayT, t); bot = mix(twB, dayB, t); }
    else { var n = clamp(-alt / .3, 0, 1); top = mix(twT, nT, n); bot = mix(twB, nB, n); }
    // overcast desaturates toward grey; storms go dark
    var dayGreyT = [102, 112, 124], dayGreyB = [152, 160, 170], nGreyT = [11, 13, 19], nGreyB = [26, 30, 38];
    var dl = clamp((alt + .3) / .7, 0, 1);
    var gT = mix(nGreyT, dayGreyT, dl), gB = mix(nGreyB, dayGreyB, dl);
    var k = Math.pow(cloud, 1.3) * .88;
    top = mix(top, gT, k); bot = mix(bot, gB, k);
    if (storm > 0) { top = mix(top, mix([22, 25, 34], [6, 7, 11], 1 - dl), storm * .9); bot = mix(bot, mix([58, 66, 80], [14, 16, 24], 1 - dl), storm * .8); }
    return [top, bot];
  }

  function moonPhase() {
    var days = (Date.now() / 86400000 - 10957.7) % 29.530588; if (days < 0) days += 29.530588; // 2000-01-06 new moon
    return days / 29.530588;
  }

  function drawSky(c, S) {
    var w = E.w, h = E.h, cc = skyColors(S.alt, S.cloud, S.storm);
    var g = c.createLinearGradient(0, 0, 0, h * .85); g.addColorStop(0, rgb(cc[0])); g.addColorStop(1, rgb(cc[1]));
    c.fillStyle = g; c.fillRect(0, 0, w, h);
    S.cc = cc;
  }

  function celestialXY(S) {
    var horizon = E.h * .74, span = E.h * .62;
    var x = E.w * (.1 + S.p * .8);
    var y = horizon - Math.sin(S.p * Math.PI) * span * (S.isDay ? 1 : .9);
    return [x, y];
  }

  function drawStars(c, S) {
    var vis = clamp((-S.alt + .05) * 3.2, 0, 1) * (1 - S.cloud * .92); if (vis < .02) return;
    for (var i = 0; i < E.stars.length; i++) {
      var s = E.stars[i], tw = .55 + .45 * Math.sin(E.time * s.sp + s.ph);
      c.fillStyle = 'rgba(225,235,255,' + (vis * tw).toFixed(3) + ')'; c.beginPath(); c.arc(s.x, s.y, s.r, 0, TAU); c.fill();
    }
    // occasional shooting star on clear nights
    if (S.cloud < .35 && vis > .5) {
      if (!E.shoot && E.time > E.nextShoot) { E.shoot = { x: E.w * (.2 + Math.random() * .6), y: E.h * (.05 + Math.random() * .25), t: 0 }; E.nextShoot = E.time + 18 + Math.random() * 25; }
      if (E.shoot) {
        var sh = E.shoot; sh.t += E.dt * 1.6; var a = 1 - sh.t; if (a <= 0) { E.shoot = null; } else {
          var x2 = sh.x + sh.t * E.w * .18, y2 = sh.y + sh.t * E.h * .12;
          var gr = c.createLinearGradient(x2, y2, x2 - E.w * .07, y2 - E.h * .045); gr.addColorStop(0, 'rgba(255,255,255,' + a + ')'); gr.addColorStop(1, 'rgba(255,255,255,0)');
          c.strokeStyle = gr; c.lineWidth = 1.6; c.beginPath(); c.moveTo(x2, y2); c.lineTo(x2 - E.w * .07, y2 - E.h * .045); c.stroke();
        }
      }
    }
  }

  function drawSun(c, S) {
    if (!S.isDay && S.alt < -.05) return;
    var xy = celestialXY(S), x = xy[0], y = xy[1], R = Math.min(E.w, E.h) * .052;
    var vis = (1 - S.cloud * .78) * clamp((S.alt + .12) * 4, 0, 1); if (vis < .03) return;
    var warm = clamp(1 - S.alt / .45, 0, 1), col = mix([255, 244, 214], [255, 150, 70], warm);
    var glow = c.createRadialGradient(x, y, R * .3, x, y, R * (7 + warm * 3));
    glow.addColorStop(0, rgb(col, .65 * vis)); glow.addColorStop(.25, rgb(col, .25 * vis)); glow.addColorStop(1, rgb(col, 0));
    c.fillStyle = glow; c.fillRect(0, 0, E.w, E.h);
    if (S.cloud < .5) { // soft god-ray fan
      c.save(); c.translate(x, y); c.rotate(E.time * .03);
      for (var i = 0; i < 14; i++) { c.rotate(TAU / 14); var rg = c.createLinearGradient(0, 0, R * 9, 0); rg.addColorStop(0, rgb(col, .1 * vis)); rg.addColorStop(1, rgb(col, 0)); c.fillStyle = rg; c.beginPath(); c.moveTo(0, -R * .35); c.lineTo(R * 9, -R * .9); c.lineTo(R * 9, R * .9); c.lineTo(0, R * .35); c.closePath(); c.fill(); }
      c.restore();
    }
    var body = c.createRadialGradient(x - R * .25, y - R * .25, R * .1, x, y, R);
    body.addColorStop(0, rgb([255, 255, 245], vis)); body.addColorStop(1, rgb(col, vis));
    c.fillStyle = body; c.beginPath(); c.arc(x, y, R, 0, TAU); c.fill();
  }

  function drawMoon(c, S) {
    if (S.isDay && S.alt > .1) return;
    var xy = celestialXY(S), x = xy[0], y = xy[1], R = Math.min(E.w, E.h) * .05;
    var vis = clamp((-S.alt + .1) * 4, 0, 1) * (1 - S.cloud * .8); if (vis < .03) return;
    var glow = c.createRadialGradient(x, y, R * .5, x, y, R * 6);
    glow.addColorStop(0, 'rgba(170,196,255,' + (.35 * vis) + ')'); glow.addColorStop(1, 'rgba(170,196,255,0)');
    c.fillStyle = glow; c.fillRect(0, 0, E.w, E.h);
    c.save(); c.beginPath(); c.arc(x, y, R, 0, TAU); c.clip();
    c.globalAlpha = vis;
    var body = c.createRadialGradient(x - R * .3, y - R * .3, R * .1, x, y, R); body.addColorStop(0, '#f7f9ff'); body.addColorStop(1, '#c9d4ee');
    c.fillStyle = body; c.fillRect(x - R, y - R, R * 2, R * 2);
    c.fillStyle = 'rgba(120,135,170,.28)';
    [[-.3, -.15, .22], [.25, .2, .17], [.1, -.4, .12], [-.2, .35, .1]].forEach(function (m) { c.beginPath(); c.arc(x + m[0] * R, y + m[1] * R, m[2] * R, 0, TAU); c.fill(); });
    var ph = moonPhase(), f = (1 - Math.cos(ph * TAU)) / 2, dir = ph < .5 ? -1 : 1;
    c.fillStyle = 'rgba(6,10,26,.93)'; c.beginPath(); c.arc(x + dir * 2 * R * f, y, R * 1.02, 0, TAU); c.fill();
    c.restore(); c.globalAlpha = 1;
  }

  function drawClouds(c, S, dt, layerMin, layerMax) {
    if (!E.sprites) return;
    var n = Math.round(2 + S.cloud * 11), wind = S.wind, W = E.w, H = E.h;
    var base = clamp(W / 900, .5, 1.05);
    for (var i = 0; i < n && i < E.clouds.length; i++) {
      var cl = E.clouds[i]; if (cl.layer < layerMin || cl.layer >= layerMax) continue;
      var sp = (5 + wind * 2.2) * (.4 + cl.layer * .9) * cl.sp;
      cl.x += (sp / W) * dt; if (cl.x > 1.35) cl.x = -.35;
      var sc = base * cl.s * (.62 + cl.layer * .4) * (1 + S.cloud * .25);
      var sw = 340 * sc, sh = 150 * sc;
      var y = H * (cl.y * (1 - S.cloud * .25) + S.storm * .06) - sh * .3;
      var a = clamp(.35 + S.cloud * .7, 0, 1) * (cl.layer * .3 + .7);
      if (S.cloud < .3) a *= .85;
      c.globalAlpha = a; c.drawImage(E.sprites[cl.spr], cl.x * W - sw * .5, y, sw, sh);
    }
    c.globalAlpha = 1;
  }

  function hillColors(S) {
    var alt = S.alt, dl = clamp((alt + .25) / .6, 0, 1);
    var day = [[74, 118, 128], [50, 92, 78], [32, 70, 48]], night = [[14, 24, 40], [10, 22, 30], [8, 16, 22]];
    var gold = [[150, 110, 120], [110, 84, 84], [64, 58, 50]];
    var out = [];
    for (var i = 0; i < 3; i++) {
      var c = mix(night[i], day[i], dl);
      var gl = clamp(1 - Math.abs(alt - .1) / .16, 0, 1); c = mix(c, gold[i], gl * .55);
      var snow = S.snowGround; if (snow > 0) c = mix(c, mix([196, 208, 224], [236, 242, 250], i / 2), snow * (.8 + dl * .2) * (dl > .1 ? 1 : .55));
      c = mix(c, mix(c, [70, 78, 88], .4), S.cloud * .4);
      out.push(c);
    }
    return out;
  }

  function drawHills(c, S) {
    var cols = hillColors(S), w = E.w, h = E.h;
    for (var L = 0; L < 3; L++) {
      var pts = E.hills[L].pts;
      var g = c.createLinearGradient(0, h * .6, 0, h); g.addColorStop(0, rgb(mix(cols[L], S.cc[1], L === 0 ? .32 : .12))); g.addColorStop(1, rgb(mix(cols[L], [0, 0, 0], .35)));
      c.fillStyle = g; c.beginPath(); c.moveTo(0, h); for (var i = 0; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]); c.lineTo(w, h); c.closePath(); c.fill();
      if (L === 1) drawTrees(c, S, cols[1]);
    }
    // wet sheen on the ground while it rains
    if (S.rainAmt > .05) {
      var sh = c.createLinearGradient(0, h * .84, 0, h); sh.addColorStop(0, 'rgba(190,210,235,0)'); sh.addColorStop(.5, 'rgba(190,210,235,' + (.12 * S.rainAmt * clamp(S.alt + .5, .2, 1)) + ')'); sh.addColorStop(1, 'rgba(190,210,235,0)');
      c.fillStyle = sh; c.fillRect(0, h * .84, w, h * .16);
    }
  }
  function drawTrees(c, S, hillCol) {
    var col = mix(hillCol, [4, 14, 10], .55), wind = clamp(S.wind / 25, 0, 1.6) * (1 + .3 * Math.sin(E.time * .4));
    c.fillStyle = rgb(col);
    for (var i = 0; i < E.trees.length; i++) {
      var t = E.trees[i], th = 26 * t.s, tw = 8.5 * t.s, sway = Math.sin(E.time * 1.6 + t.ph) * wind * 2 * t.s + wind * 1.2 * t.s;
      // three overlapping tiers give a pine silhouette instead of a plain triangle
      for (var tier = 0; tier < 3; tier++) {
        var ty = t.y - th * (tier * .27), tww = tw * (1 - tier * .24), top = ty - th * .5, sx = sway * (tier + 1) / 3;
        c.beginPath(); c.moveTo(t.x - tww, ty); c.lineTo(t.x + sx, top - tier * 1.5); c.lineTo(t.x + tww, ty); c.closePath(); c.fill();
      }
      if (S.snowGround > .3) { c.fillStyle = rgb([236, 242, 250], .55 * S.snowGround); c.beginPath(); c.moveTo(t.x - tw * .5, t.y - th * .3); c.lineTo(t.x + sway * .6, t.y - th * .95); c.lineTo(t.x + tw * .5, t.y - th * .3); c.closePath(); c.fill(); c.fillStyle = rgb(col); }
    }
  }

  function drawFog(c, S) {
    if (S.fog < .03) return;
    for (var i = 0; i < 4; i++) {
      var y = E.h * (.52 + i * .1), x = ((E.time * (3 + i * 2) * (1 + S.wind * .05)) % (E.w * 1.6)) - E.w * .3 + (i % 2 ? E.w * .3 : 0);
      c.save(); c.translate(E.w * .5 + Math.sin(E.time * .07 + i) * E.w * .1 + (x - E.w * .5) * .15, y); c.scale(1, .22);
      var g = c.createRadialGradient(0, 0, 0, 0, 0, E.w * .75);
      var tone = S.alt > -.05 ? [214, 222, 230] : [60, 72, 96];
      g.addColorStop(0, rgb(tone, .34 * S.fog)); g.addColorStop(1, rgb(tone, 0)); c.fillStyle = g; c.beginPath(); c.arc(0, 0, E.w * .75, 0, TAU); c.fill(); c.restore();
    }
    var v = c.createLinearGradient(0, E.h * .35, 0, E.h); v.addColorStop(0, 'rgba(200,210,220,0)'); v.addColorStop(1, 'rgba(200,210,220,' + (.26 * S.fog) + ')'); c.fillStyle = v; c.fillRect(0, E.h * .35, E.w, E.h * .65);
  }

  function drawRain(c, S, dt) {
    var amt = S.rainAmt; if (amt < .02) return;
    var count = Math.floor(RAIN_MAX * clamp(amt / 2.2, 0, 1) * clamp(E.w * E.h / 60000, .5, 1.6)); count = Math.min(count, RAIN_MAX);
    var gust = 1 + .35 * Math.sin(E.time * .35) + .2 * Math.sin(E.time * 1.1);
    var slant = clamp(S.wind * gust / 38, 0, .95); // tan(angle)
    var W = E.w, H = E.h, tone = S.alt > -.1 ? '205,222,245' : '150,175,220';
    c.lineCap = 'round';
    var buckets = [[], [], []];
    for (var i = 0; i < count; i++) {
      var d = E.rain[i], v = (520 + 620 * d.z) * (H / 160) * .55; // px/s scaled to card height
      d.y += (v * dt) / H; d.x += (v * slant * dt) / W;
      var gy = .8 + d.gy * .18;
      if (d.y >= gy) {
        if (d.z > .55 && E.splashes.length < 60) E.splashes.push({ x: d.x * W, y: gy * H, r: 1, max: 3 + d.z * 6, a: .5 * d.z });
        d.y = -.05 - Math.random() * .2; d.x = Math.random() * (1 + slant * .6) - slant * .3; d.z = .25 + Math.random() * .75; d.gy = Math.random();
      }
      buckets[d.z < .5 ? 0 : d.z < .8 ? 1 : 2].push(d);
    }
    var widths = [.7, 1.1, 1.6], alphas = [.22, .38, .6];
    for (var b = 0; b < 3; b++) {
      c.strokeStyle = 'rgba(' + tone + ',' + alphas[b] + ')'; c.lineWidth = widths[b]; c.beginPath();
      for (var j = 0; j < buckets[b].length; j++) {
        var p = buckets[b][j], len = (7 + 13 * p.z) * clamp(H / 150, .7, 1.7), x = p.x * W, y = p.y * H;
        c.moveTo(x, y); c.lineTo(x - slant * len, y - len);
      }
      c.stroke();
    }
    // ripples where drops hit the ground
    c.lineWidth = 1;
    for (var s = E.splashes.length - 1; s >= 0; s--) {
      var sp = E.splashes[s]; sp.r += dt * 26; var life = 1 - sp.r / sp.max; if (life <= 0) { E.splashes.splice(s, 1); continue; }
      c.strokeStyle = 'rgba(' + tone + ',' + (sp.a * life) + ')'; c.beginPath(); c.ellipse(sp.x, sp.y, sp.r, sp.r * .32, 0, 0, TAU); c.stroke();
    }
  }

  function drawSnow(c, S, dt) {
    var amt = S.snowAmt; if (amt < .02) return;
    var count = Math.min(SNOW_MAX, Math.floor(SNOW_MAX * clamp(amt / 2.4, 0, 1) * clamp(E.w * E.h / 60000, .5, 1.5)));
    var W = E.w, H = E.h, gust = 1 + .4 * Math.sin(E.time * .3) + .25 * Math.sin(E.time * .9), wv = S.wind * gust * 2.4;
    for (var i = 0; i < count; i++) {
      var f = E.snow[i], fall = (26 + 52 * f.z) * (H / 150) * .7;
      f.y += (fall * dt) / H; f.x += ((Math.sin(E.time * f.sp + f.ph) * (10 + 12 * f.z) + wv) * dt) / W;
      if (f.y > .98) { f.y = -.03; f.x = Math.random() * 1.2 - .1; }
      if (f.x > 1.05) f.x = -.05; else if (f.x < -.05) f.x = 1.05;
      var r = (.8 + 2.4 * f.z) * clamp(H / 150, .8, 1.5), a = .45 + .5 * f.z, x = f.x * W, y = f.y * H;
      if (r > 2.3) { var g = c.createRadialGradient(x, y, 0, x, y, r * 2.1); g.addColorStop(0, 'rgba(255,255,255,' + a + ')'); g.addColorStop(.45, 'rgba(255,255,255,' + a * .55 + ')'); g.addColorStop(1, 'rgba(255,255,255,0)'); c.fillStyle = g; c.beginPath(); c.arc(x, y, r * 2.1, 0, TAU); c.fill(); }
      else { c.fillStyle = 'rgba(255,255,255,' + a + ')'; c.beginPath(); c.arc(x, y, r, 0, TAU); c.fill(); }
    }
  }

  function bolt(w, h) {
    var x = w * (.22 + Math.random() * .56), y = 0, segs = [], branches = [], gy = h * .8;
    var dir = (Math.random() - .5) * .6;
    while (y < gy) {
      var ny = y + h * (.05 + Math.random() * .08), nx = x + (Math.random() - .5 + dir * .3) * w * .09;
      segs.push([x, y, nx, ny]);
      if (Math.random() < .28 && y > h * .1) { var bx = nx, by = ny, bd = (Math.random() < .5 ? -1 : 1); for (var k = 0; k < 3; k++) { var bx2 = bx + bd * w * (.02 + Math.random() * .04), by2 = by + h * (.04 + Math.random() * .05); branches.push([bx, by, bx2, by2]); bx = bx2; by = by2; } }
      x = nx; y = ny;
    }
    return { segs: segs, branches: branches };
  }
  function drawLightning(c, S, dt) {
    var L = E.lightning;
    if (S.storm > .3) {
      L.next -= dt;
      if (L.next <= 0) { L.bolt = bolt(E.w, E.h); L.flash = 1; L.second = Math.random() < .6 ? .13 : 0; L.next = 2.2 + Math.random() * 6.5; }
      if (L.second > 0) { L.second -= dt; if (L.second <= 0) { L.flash = .85; if (!L.bolt) L.bolt = bolt(E.w, E.h); } }
    }
    if (L.flash > 0) {
      c.fillStyle = 'rgba(200,214,255,' + (L.flash * .32) + ')'; c.fillRect(0, 0, E.w, E.h);
      if (L.bolt && L.flash > .25) {
        c.save(); c.lineCap = 'round'; c.lineJoin = 'round'; c.shadowColor = '#b8ccff'; c.shadowBlur = 16;
        c.strokeStyle = 'rgba(255,255,255,' + clamp(L.flash * 1.2, 0, 1) + ')'; c.lineWidth = 2.2; c.beginPath();
        L.bolt.segs.forEach(function (s) { c.moveTo(s[0], s[1]); c.lineTo(s[2], s[3]); }); c.stroke();
        c.lineWidth = 1.1; c.beginPath(); L.bolt.branches.forEach(function (s) { c.moveTo(s[0], s[1]); c.lineTo(s[2], s[3]); }); c.stroke();
        c.restore();
      }
      L.flash -= dt * 3.4; if (L.flash <= 0) { L.flash = 0; L.bolt = null; }
    }
  }

  /* ------------------------------------------------------------- main loop */
  function approach(cur, tgt, k) { return cur + (tgt - cur) * k; }

  function frame(ts) {
    E.raf = 0;
    var cv = E.canvas; if (!cv || !cv.isConnected) { E.canvas = null; return; }
    if (document.hidden || cv.clientWidth === 0) { E.raf = requestAnimationFrame(frame); return; }
    if (ts - E.last < 33) { E.raf = requestAnimationFrame(frame); return; }  // ~30fps: this layers ~10 draw passes per frame
    var dt = E.last ? Math.min((ts - E.last) / 1000, .06) : .016; E.last = ts; E.dt = dt; E.time += dt;
    if (!E.tgt || E.time - E.lastDerive > 3) { E.tgt = deriveTarget(); E.lastDerive = E.time; updateTag(); }
    var T = E.tgt, C = E.cur, k = clamp(dt * (REDUCED ? 5 : 1.4), 0, 1);
    if (E.snap) {
      E.snap = false; k = 1;
      C.alt = T.alt; C.cloud = T.cloud; C.fog = T.fog; C.wind = T.wind;
      C.rainAmt = (T.kind === 'rain' || T.kind === 'storm') ? T.intensity : 0; C.snowAmt = T.kind === 'snow' ? T.intensity : 0; C.storm = T.kind === 'storm' ? 1 : 0;
    }
    C.cloud = approach(C.cloud, T.cloud, k); C.fog = approach(C.fog, T.fog, k); C.wind = approach(C.wind, T.wind, k);
    C.alt = approach(C.alt, T.alt, k * .7);
    var wantRain = (T.kind === 'rain' || T.kind === 'storm') ? T.intensity : 0, wantSnow = T.kind === 'snow' ? T.intensity : 0;
    C.rainAmt = approach(C.rainAmt, wantRain, k); C.snowAmt = approach(C.snowAmt, wantSnow, k); C.storm = approach(C.storm, T.kind === 'storm' ? 1 : 0, k);
    var S = { alt: C.alt, cloud: C.cloud, fog: C.fog, wind: C.wind, storm: C.storm, rainAmt: C.rainAmt, snowAmt: C.snowAmt, p: T.p, isDay: T.isDay, snowGround: clamp(C.snowAmt / 1.2, 0, 1) };
    var dark = clamp(Math.max(C.storm, C.rainAmt > 0 ? .5 + Math.min(C.rainAmt, 1.6) * .18 : 0, (C.cloud - .8) * 2), 0, 1);
    var key = ambientKey(S.alt, dark); if (key !== E.spriteKey) { E.spriteKey = key; buildSprites(S.alt, dark); }
    var c = E.ctx;
    c.setTransform(E.dpr, 0, 0, E.dpr, 0, 0);
    drawSky(c, S); drawStars(c, S); drawSun(c, S); drawMoon(c, S);
    drawClouds(c, S, dt, 0, .5); drawHills(c, S); drawClouds(c, S, dt, .5, 1.01);
    if (S.cloud > .6) { var ov = c.createLinearGradient(0, 0, 0, E.h * .6); var dc = S.alt > 0 ? [58, 64, 76] : [8, 10, 16]; ov.addColorStop(0, rgb(dc, clamp((S.cloud - .55) * (.5 + S.storm * .5), 0, .8))); ov.addColorStop(1, rgb(dc, 0)); c.fillStyle = ov; c.fillRect(0, 0, E.w, E.h * .6); }
    drawFog(c, S); drawRain(c, S, dt); drawSnow(c, S, dt); drawLightning(c, S, dt);
    // gentle vignette
    var vg = c.createRadialGradient(E.w / 2, E.h / 2, Math.min(E.w, E.h) * .3, E.w / 2, E.h / 2, Math.max(E.w, E.h) * .75); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.35)'); c.fillStyle = vg; c.fillRect(0, 0, E.w, E.h);
    if (REDUCED && E.time > .6) { return; } // one settled frame is enough for reduced motion
    E.raf = requestAnimationFrame(frame);
  }

  function updateTag() {
    if (!E.tag || !E.tgt) return;
    var T = E.tgt, names = { clear: 'Clear', cloud: 'Cloudy', rain: 'Rain', storm: 'Thunderstorm', snow: 'Snow', fog: 'Fog' };
    var when = T.isDay ? (T.alt < .3 ? (T.p < .5 ? 'Sunrise' : 'Sunset') : 'Day') : 'Night';
    var bits = [override && override.label ? override.label : (T.label || names[T.kind]), when];
    if (Math.round(T.wind) > 0) bits.push(Math.round(T.wind) + ' mph');
    E.tag.textContent = bits.join(' · ');
  }

  /* ------------------------------------------------------------- attach / resize */
  function size() {
    var cv = E.canvas; if (!cv) return;
    var r = cv.getBoundingClientRect(); var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
    if (w === E.w && h === E.h && dpr === E.dpr && E.hills) return;
    E.w = w; E.h = h; E.dpr = dpr; cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); buildScenery();
  }
  var ro = (typeof ResizeObserver !== 'undefined') ? new ResizeObserver(function () { size(); }) : null;

  function attach() {
    var sky = document.querySelector('#weatherSimViz .weather-sky'); if (!sky) return;
    var cv = sky.querySelector('.wx-canvas'); if (cv && cv === E.canvas) return;
    if (!cv) {
      cv = document.createElement('canvas'); cv.className = 'wx-canvas'; cv.setAttribute('aria-hidden', 'true'); sky.insertBefore(cv, sky.firstChild);
      var tag = document.createElement('div'); tag.className = 'wx-tag'; sky.appendChild(tag); E.tag = tag;
    }
    sky.classList.add('wx-on');
    if (E.canvas && ro) ro.unobserve(E.canvas);
    E.canvas = cv; E.ctx = cv.getContext('2d'); E.w = 0; E.h = 0;
    if (ro) ro.observe(cv);
    size(); E.tgt = null; E.last = 0;
    if (!E.raf) E.raf = requestAnimationFrame(frame);
  }

  function boot() {
    var host = document.getElementById('weatherSimViz');
    if (host && typeof MutationObserver !== 'undefined') new MutationObserver(attach).observe(host, { childList: true });
    attach(); setInterval(attach, 2500);
    document.addEventListener('visibilitychange', function () { if (!document.hidden && !E.raf && E.canvas) { E.last = 0; E.raf = requestAnimationFrame(frame); } });
  }

  /* ------------------------------------------------------------- public API + palette hooks */
  function preview(name) {
    if (!name || name === 'live') { override = null; } else if (PRESETS[name]) { override = {}; for (var k in PRESETS[name]) override[k] = PRESETS[name][k]; override.label = name; } else return false;
    E.tgt = null; E.snap = true; E.lightning.next = .4; return true;
  }
  window.spac3WeatherFX = { preview: preview, presets: Object.keys(PRESETS) };
  (window.v2ExtraCommands = window.v2ExtraCommands || []).push(function () {
    var list = [{ g: '☁', grp: 'Weather FX', name: 'Weather FX: live weather', run: function () { preview('live'); if (window.v2Toast) window.v2Toast('Weather FX', 'showing live conditions', 'info', 1800); } }];
    Object.keys(PRESETS).forEach(function (n) {
      list.push({ g: '☁', grp: 'Weather FX', name: 'Weather FX: ' + n, run: function () {
        preview(n);
        try { if (typeof showTab === 'function') showTab('signals'); } catch (e) { /* ignore */ }
        setTimeout(function () { var s = document.querySelector('#weatherSimViz'); if (s && s.scrollIntoView) s.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, 150);
      } });
    });
    return list;
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
