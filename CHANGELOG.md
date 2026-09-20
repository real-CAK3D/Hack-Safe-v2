# Changelog

## 2.2.0

### New "Deck" tab (`web/deck.js`, `web/deck.css`)
- Animated radial gauges (CPU, memory, disk, temperature) with tweened needles and threshold colours.
- Live telemetry chart backed by a new server-side sampler (`/api/metrics`, 1 h of history, so charts are filled the moment you open them): range switch, series toggles, hover crosshair with tooltip, gradient fills.
- Sweeping signal radar (Wi-Fi / Bluetooth / LAN) with fading blips, hover tooltips and click-to-select.
- Wi-Fi channel spectrum analyzer with overlapping signal curves (co-channel interference at a glance).
- Draggable force-directed network graph with animated traffic dots.
- Sortable, filterable device table; top-processes table with bars; storage rings; filterable event timeline; ECG-style system pulse; alert posture summary.
- "Demo data" switch (or `?demo=1`) fills empty panels with clearly labelled sample data.

### Visual FX + console (`web/fx.js`)
- Constellation background that reacts to the cursor, card spotlight, 3D tilt on tiles/gauges, one-time boot sequence.
- Drop-down terminal on `` ` ``: `status`, `health`, `top`, `wifi`, `bt`, `lan`, `scan`, `theme`, `weather`, `goto`, `demo`, and more (tab-completion, history).
- All of it is optional and off under `prefers-reduced-motion`.

### Reliability and security fixes
- Request guard: cross-origin / cross-site POSTs and DNS-rebinding Host headers are refused on `/api` (the control endpoints previously accepted requests from any web page).
- `service_watchdog` plugin crashed on every status update; fixed.
- Action endpoints (spicy tools, lab software) dropped the connection on error; missing or hung system tools no longer raise, and any unexpected handler error now returns JSON instead of a dead socket.
- First page load no longer waits up to 15 s for real data ("warming"): the UI re-polls every 2.5 s until the server is ready.
- All 41 POST routes fuzzed with bad input: 0 server errors. 62+ tests.

## 2.1.0

### Weather Ops: new canvas weather engine (`web/weatherfx.js`)
- Replaces the CSS-only sky with a layered simulation driven by the live weather data (summary, wind, sunrise/sunset).
- Sky colour follows sun altitude (night, twilight, golden hour, day) and darkens with overcast/storms.
- Cumulus-style clouds with parallax drift that speeds up with wind; real moon phase, twinkling stars, shooting stars.
- Depth-sorted rain slanted by gusting wind with ground splashes/ripples and wet-ground sheen; swaying snow with accumulation; drifting fog; forked lightning with sky flash.
- Hills and swaying pines, smooth transitions when conditions change, pauses when hidden, respects reduced-motion.
- Command palette (`Ctrl/Cmd+K`) has "Weather FX: ..." presets (clear, rain, thunderstorm, snow, blizzard, fog, night, golden hour) to preview any condition.

### Proton map
- Pins used to be placed by hand-tuned percentages of a box that did not match the map artwork, so they drifted into the ocean. They now sit on an aspect-locked canvas and use anchors measured from the SVG itself (each verified inside its country's land shape), so they stay on the right country at any panel size or zoom.
- New pin style (centred dot, pulse ring, hover label). Fixed loose profile matching that highlighted the wrong pins (for example "Fastest country" lit ES and TR).

## 2.0.0

### New UI (web/v2.css, web/v2.js: additive, loaded after the original UI)
- Glass-style redesign: rounded translucent cards, gradient accents, animated aurora background, pill tab bar, breathing halo behind the ghost face.
- Live **vitals strip**: CPU, memory, disk, temperature, network, uptime, signal counts and alert level, each with a sparkline and threshold colouring.
- **Command palette** (`Ctrl/Cmd+K` or `/`): jump to any tab or card, run scans, refresh, export, change theme.
- Keyboard shortcuts: `1`-`6` tabs, `R` refresh, `T`/`Shift+T` themes, `F` fullscreen, `?` help.
- Four new themes (aurora, synthwave, glacier, mono) plus the six originals; `T` cycles them.
- Toast notifications for alerts, service problems, thermal events and alert-level changes.
- Live connection pill (LIVE / RETRYING / OFFLINE with latency) driven by the new `/api/health`.
- Collapsible cards (remembered per browser), CRT scanline and compact-density toggles, status snapshot export (config omitted).
- Responsive/mobile layout, focus rings, reduced-motion support, styled scrollbars.

### Backend
- Cross-platform system metrics (`spac3ghost/hostinfo.py`): CPU, memory, disk, uptime, IPs and top processes now work on Windows (and degrade per-field elsewhere) instead of the whole status failing.
- `/api/health` liveness endpoint; `__version__`.
- No more fake "service offline" events on hosts without systemd.
- Portable paths (`spac3ghost/paths.py`), configurable bind host/port, camera fallback without OpenCV.

### Fixes
- Service-down events were shadowed by time-of-day moods; "lonely" mood restored.
- Hard-coded hotspot password and tailnet hostname removed from defaults.
- Tests no longer depend on live config or the clock (45+ tests).
