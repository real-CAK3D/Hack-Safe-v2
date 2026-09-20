# Changelog

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
