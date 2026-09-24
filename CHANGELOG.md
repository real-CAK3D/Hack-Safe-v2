# Changelog

## 2.6.0

Bug-fix pass after a concurrent session's "restore header / collapse Signals / drop duplicate
Cesium bundle" merge introduced a couple of regressions, plus a couple of pre-existing bugs
surfaced by testing everything live on the physical Pi.

### Fixed
- **Signals tab was empty.** The new collapsible `<details class="signals-group">` wrapper
  (from the concurrent merge) never got a `grid-column: 1 / -1` rule, so each group sat in a
  single ~106px track of the outer 12-column grid instead of spanning full width -- squeezing
  every card inside it down to near-zero width. Fixed in `web/v2.css`.
- **God's Eye View: "cross origin" error.** Several routes the globe's own app actually calls
  (`/api/openai/hud-summary`, `/api/realtime/*`, `/api/military-installations`,
  `/api/weather-effects` -- confirmed against its `vite.config.js` middleware mounts) weren't in
  `GODSEYE_API_PREFIXES`, so they fell through to Hack-Safe's own CSRF guard instead of being
  proxied, which rejects them as "cross-origin request blocked". Added them to the allowlist.
- **Camera feed went stale/black after Arm Vision.** `refreshCameraFrame`/`scheduleCamera` in
  `web/app.js` still gated live polling on `activeTab === 'vision'` -- a tab that no longer exists
  since Vision was merged into Externals. The check never matched, so the feed only ever fetched
  one single frame (on arm/switch/scan) and then never updated again. Now gates on `'externals'`.
- **CYD Buddy settings / theBAK3RY camera: not bugs.** Verified live -- CYD Buddy settings do
  save and queue correctly (the console explicitly says "NO CYD DHCP LEASE YET", meaning the
  physical Buddy isn't currently on the Wu-Tang LAN); theBAK3RY's host answers ping fine but
  nothing is listening on its camera-snapshot port 8091, so its own snapshot server needs
  checking on that Pi, not this one.

### New
- **Editable vision history.** Each Vision History row now has a delete button
  (`delete_vision_history_entry` in `spac3ghost/vision.py`, `/api/vision/history/delete`) to
  remove a single false-positive/irrelevant entry and its snapshot, instead of only being able to
  wipe the entire history at once.

## 2.5.0

Performance pass after the physical Pi 5 (Elecrow CrowPi, 7" touchscreen) was struggling badly.
Diagnosed live over SSH rather than guessing: Hack-Safe's own process was only using ~2.8% CPU --
the real damage was a mis-scoped feature and a system-wide `--disable-gpu-rasterization` flag on
the kiosk browser forcing all canvas rendering onto the CPU (flagged below, not yet changed).

### Fixed
- **God's Eye View's live server never stopped.** `godseye-live.service` (a Vite dev server for
  the embedded Cesium globe) was enabled at boot and had been running continuously for 32+ hours,
  averaging ~68% of one CPU core the whole time, regardless of whether anyone had the globe open.
  The pre-built static shell already existed on disk (`web/godseye-app`, checked in from an
  earlier snapshot) but nothing served it. Opening `/godseye-live` now serves that shell directly
  -- no process required, loads in ~1ms instead of depending on a hot dev server. Only the live
  tracking APIs (opensky, ais-live, cctv, overpass, ...) still need `godseye-live.service`; those
  routes now start it on first hit (`ensure_godseye_running` in `spac3ghost/controls.py`) and a
  30s-interval watchdog (`godseye_idle_check`) stops it again after 5 minutes without a live-data
  request. The service's boot-time auto-start was also disabled on the Pi directly.
- **Status collectors could oversubscribe the Pi's 4 cores.** `_collect_status_payload()` spun up
  one thread per collector (10+, several of which fork their own subprocesses) every ~20s
  regardless of core count; `lab_toys_status()`'s own internal pool did the same with ~9 more.
  Both are now bounded to `os.cpu_count()`.
- **`lab_toys_status()` ran on every status cycle even though the Lab tab is rarely open.** It fans
  out ~9 of its own subprocess probes (Tailscale-hosted software checks, hardware detection). Now
  cached for 90s instead of re-running on the ~20s status cadence.
- **EarnApp removed from the Pi** at the user's request -- it was running two always-on services
  selling spare CPU/bandwidth to a third party for no benefit to this project.

### Changed
- Every continuous decorative canvas loop (Signals/Deck chart+radar engine, the Deck tab's five
  widgets, the constellation background, the weather ambient animation) is now capped to ~30fps
  instead of uncapped 60fps. No visible difference at these animation speeds; roughly halves their
  CPU/GPU cost, which matters most on a Pi rendering its own kiosk display.
- GPS tilt polling only runs while the Signals tab is actually open, and backed off from 1.5s to
  3s; the local camera preview backed off from ~2.2fps to ~1.4fps polling.

### Known, not yet acted on
- The kiosk launcher (`start-hack-safe-v2.sh`) opens Chromium with
  `--disable-gpu-rasterization`, which forces every canvas/CSS composite in the browser onto the
  CPU instead of the Pi 5's GPU. This is very likely a significant chunk of the remaining
  sluggishness, but the flag may have been added to work around a real GPU-driver crash on this
  hardware, and it can't be safely toggled without watching the actual screen for a crash/black
  screen. Worth revisiting with the user present at the device.
- This Pi is also running a full personal server stack alongside the kiosk dashboard (9 Docker
  containers, Ollama, Jellyfin, a VNC server, Syncthing, vsftpd) sharing the same 4 cores; none of
  that is Hack-Safe's to change.
- `vcgencmd get_throttled` reports under-voltage/throttling have occurred this boot -- a power
  delivery issue (PSU/cabling/case), not something software can fix.

## 2.4.0

Perfecting the Spac3-Gh0st face/voice and the Signals tab, per this session's request to make
the personality "pwnagotchi-perfect out of the box" and to fix the top dock, heartbeat, GPS radar
and Weather Ops radar.

### Fixed
- **Phrases repeated constantly.** `Spac3Voice` was recreated on almost every call, so its
  instance-level "don't repeat" tracking never had a chance to do anything -- every phrase pick
  was a fresh coin flip over the same small pool. Replaced with a module-level shuffle-bag
  (`_pick_no_repeat` in `spac3ghost/personality.py`): the most-recently-used ~2/3 of a phrase
  bank is held back before a repeat is allowed, independent of how often the voice object itself
  gets rebuilt. Also grew several thin phrase banks (idle, gps fix/no-fix, hot, wifi scan,
  atmosphere/ambient banks) so the bag has more to draw from.
- **Moods didn't react to movement or a down critical service.** `choose_mood()` now returns a
  dedicated "movement" mood on a fast tilt event, and a "concerned" mood when `ssh` or
  `tailscaled` is down -- previously neither had any effect on the face at all. Indoor temperature
  now also flavors the weather-mood pool (`roomcool` / `roomwarm`) alongside the existing outdoor
  weather checks.
- **Alert Level tile ignored its own color.** The GREEN/YELLOW/ORANGE/RED text was always styled
  the same dim tone regardless of level; the tile's 4-state mapping and CSS now actually key off
  `alert.level`, with a distinct "caution" (yellow) state separate from "warn" (orange).
- **GPS/Sensors radar blips didn't sync to the sweep.** The old CSS `animation-delay` math
  (`(a/360)*-6`) never actually lined up brightening with the sweep line crossing a blip except by
  coincidence. Rewritten as a canvas widget (`drawGpsRadar` in `web/charts.js`) that computes the
  sweep angle from wall-clock time and lights/decays each blip exactly when the sweep passes it.
- **System pulse was a generic blip, not a heartbeat.** `deck.js`'s `drawPulse()` now draws an
  actual PQRST waveform (P wave, Q dip, R spike, S recovery, T wave, rest) with load-driven BPM
  and a flash on every R-wave crossing, instead of a sine-ish placeholder.

### New
- **Notification bell.** A bell icon in the header HUD collects toasts (alerts, new devices, mesh
  messages, CYD connect/disconnect, CPU/disk threshold crossings, etc.) into a persistent
  (localStorage-backed) unread-counted log you can open any time, instead of catching a toast only
  if you happened to be looking when it fired. `KINDS` in `web/v2.js` was also expanded to cover
  every real backend event kind so the bell/toast styling matches what's actually happening.
- **Weather Ops radar rebuilt.** Replaced the old static "sweep + one yellow dot" radar with a
  canvas precipitation-cell field (`drawWeatherRadar` in `web/charts.js`) that drifts along the
  live wind vector, plus Recent / Now / Upcoming filter tabs. Being honest about the limits here:
  OpenWeatherMap's free tile API only ever has *one* current-moment tile, so "Recent"/"Upcoming"
  are a stylized extrapolation along wind direction and speed, not real historical/forecast radar
  frames -- the real OpenWeather tile (when a key is configured) is still shown, but only under
  "Now" since that's the only real frame that exists. The 5-day forecast now sits beside the radar
  instead of below it (`grid-template-areas` in `style.css`); it'll show up to 5 days when the
  weather source provides them (today, wttr.in's free response typically only returns 3).
- `windDir`/`precipMm` added to `weather_status()` in `spac3ghost/collectors.py` to feed the radar's
  wind-vector drift.

### Not done (by design)
- No calendar-events feature was added -- there's no calendar data source wired into the app, and
  fabricating fake events felt worse than leaving it out. Flag if you'd like a real calendar/ICS
  feed hooked in.

## 2.3.0

Pulled in this session's CYD Buddy work from GitHub (dock/telemetry, Meshtastic gateway card,
settings console) and polished/fixed the rest of the app around it.

### Fixed
- **Weather key diagnostics.** The OpenWeather key had no schema entry in `DEFAULT_CONFIG`, so it
  silently worked by accident; a bad `config.json` would also silently wipe the *entire* saved
  config back to defaults with zero trace. Both fixed: `weather` is now a real config section,
  `load_config()` keeps serving the last good in-memory config on a parse error (and backs the bad
  file up to `*.json.corrupt` instead of overwriting it), and a new `/api/weather/keycheck` +
  "Recheck Key" button in Weather Ops actually calls OpenWeatherMap and reports *why* a key isn't
  working (missing vs. present-but-rejected vs. unreachable) instead of just "key missing".
- **CYD Buddy settings console did nothing on the device.** The dashboard could already queue a
  settings command, but the firmware (`CYD-Buddy` repo) never read it back from telemetry. Fixed
  in firmware: backlight is now a real, persisted setting (was hardcoded full brightness forever),
  idle-sleep timeout is configurable (was a hardcoded 30 minutes), and mood/personality/eye-theme/
  phrase-scroll/SD-phrase-bank all apply for real, with an ack on the next heartbeat. The console's
  own dropdowns were also fixed to use the firmware's real mood/personality names instead of
  invented ones, and a "diagnostics overlay" toggle that mapped to nothing was removed.
- **Lab tab could go completely blank.** `lab_toys_status()` ran ~9 sub-checks one after another;
  on a slow probe (or several) that could take longer than the dashboard's collector timeout,
  silently blanking every Lab card (Safety Boundaries, Hardware Docks, Software, Flipper...). It
  now runs those checks concurrently and gets a longer allowance before falling back.
- **Flipper-Inspired Toys had no UI at all.** The backend (`flipper_zero_status`/
  `flipper_feature_action`) was fully built but nothing rendered it or called it. Added the
  missing Lab -> Hardware card.
- **CYD Buddy dock was invisible in Lab -> Hardware Docks** (only had its own Externals card).
  Added a `cyd-buddy` entry there too.
- **theBAK3RY camera error was a raw exception string.** A Tailscale (100.x) snapshot URL that
  isn't reachable yet now says so explicitly (check Tailscale device approval) instead of printing
  a bare connection error.
- Removed the duplicate God's Eye View cards from Externals (it's already a launcher on the
  Dashboard's Open Tools card).

### Changed
- Every inline chart in Systems and Signals (CPU/RAM/disk/network/GPS/weather waves, etc.) now
  renders through the same canvas engine as the Deck tab's telemetry chart (gradient fill,
  smoothed line, hover tooltip) instead of the old static SVG sparkline -- one shared
  `liveWave()` choke point means every call site picked this up automatically (`web/charts.js`).
- Deck's Network Graph is now editable: add a custom node (router, switch, camera, ...), a Link
  Mode to connect any two nodes (auto-discovered or custom), double-click to rename, right-click
  to remove. Saved in the browser (localStorage), separate from the live device graph.

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
