# Spac3-Gh0st

Spac3-Gh0st is a windowed Raspberry Pi 5 hacker-companion inspired by Pwnagotchi's face, voice, plugin/event model, and RF capture workflow.

This build is for CAK3D-owned home/lab networks. It includes passive Wi-Fi/Bluetooth/LAN awareness, Pi service checks, CrowPi GPS/sensor display, and an owned-lab passive WPA capture lifecycle for monitor-capable adapters. It does not include deauth automation, evil-twin flows, credential upload, or cracking automation.

Pwnagotchi source reference cloned at: `/home/pi/src/pwnagotchi`

Pwnagotchi is GPLv3. Spac3-Gh0st includes adapted GPLv3 face/voice concepts and ships with a GPLv3 notice in `LICENSE-PWNAGOTCHI-NOTICE.md`.

## v2 highlights

- Redesigned glass UI with 10 themes (`T` cycles), live vitals strip with sparklines, toasts, collapsible cards, mobile layout.
- Command palette: `Ctrl/Cmd+K` (or `/`) to jump to any tab/card or run scans, refresh, export. `?` lists all shortcuts.
- Works on Windows/macOS/Linux, not just a Pi (cross-platform metrics, portable paths).
- `/api/health` liveness endpoint and a live connection indicator.

See [CHANGELOG.md](CHANGELOG.md) for the full list.

## Quick start (any machine)

The core dashboard is pure Python 3.10+ standard library. Hardware collectors
(GPIO, GPS, nmcli, etc.) report "n/a" on machines that lack them instead of failing.

```bash
python -m venv .venv
# Windows: .\scripts\start.ps1        Linux/macOS/Pi: ./scripts/start.sh
```

Then open <http://127.0.0.1:8765>. Optional extras:

| Need | Install |
| --- | --- |
| Camera feed / YOLO | `pip install -r requirements-vision.txt` |
| Pi GPIO / NFC | `pip install -r requirements-pi.txt` (on the Pi) |
| Run tests | `pip install -r requirements-dev.txt` then `python -m pytest` |

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `SPAC3GHOST_ROOT` | repo folder | project root (plugins, web UI) |
| `SPAC3GHOST_DATA` | `<root>/data` | config, logs of seen devices, captures (git-ignored) |
| `SPAC3GHOST_HOME` | `~` | where optional third-party apps are looked for (`~/apps/...`) |
| `SPAC3GHOST_HOST` / `SPAC3GHOST_PORT` | Tailscale IP or `127.0.0.1` / `8765` | bind address |
| `SPAC3GHOST_TAILSCALE_URL` | empty | dashboard URL shown for your tailnet |

The dashboard has no login. Only bind it to loopback or your Tailscale interface,
never to a public address.

## Launch (Raspberry Pi)

```bash
/home/pi/Desktop/System-Controls/start-spac3-gh0st.sh
```

Open manually:

```bash
cd /home/pi/spac3-gh0st
python3 -m spac3ghost.app
```

Then browse to `http://127.0.0.1:8765`.

Stop:

```bash
/home/pi/Desktop/System-Controls/stop-spac3-gh0st.sh
```

## Settings

Settings are stored at:

```text
/home/pi/spac3-gh0st/data/config.json
```

The web UI has a Settings tab where you can edit:
- Mood thresholds: warm/hot CPU, tilt timing, light/weather thresholds
- Custom faces
- Custom phrase lists
- Native plugin enable/disable flags

Saving settings reloads the native plugin system immediately.

## Native plugins

Native Spac3-Gh0st plugins live in:

```text
/home/pi/spac3-gh0st/plugins
```

Current native plugins:
- `ghost_logger` — simple callback example
- `memtemp` — native version of Pwnagotchi memtemp
- `sensor_reactor` — GPS/CrowPi sensor panel inspired by gps/webgpsmap behavior
- `session_stats` — native version of session-stats
- `logtail` — native version of logtail
- `service_watchdog` — native watchdog for Jellyfin/SSH/Tailscale/gpsd style services

## Pwnagotchi plugin compatibility

The actual Pwnagotchi plugins were inspected and summarized here:

```text
/home/pi/spac3-gh0st/docs/pwnagotchi-plugin-portability.md
```

Original Pwnagotchi plugins are discovered but not executed automatically because many assume bettercap, monitor mode, deauth, handshakes, and/or online credential-upload workflows. Spac3-Gh0st ports the pieces that fit the Pi cyberdeck and implements its own owned-lab passive capture lifecycle around monitor-mode adapters.
