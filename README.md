# Spac3-Gh0st

Spac3-Gh0st is a windowed Raspberry Pi 5 hacker-companion inspired by Pwnagotchi's face, voice, and plugin/event model.

This build is intentionally safe by default: it does passive Wi-Fi/Bluetooth/LAN awareness, Pi service checks, and CrowPi GPS/sensor display. It does not run deauth, credential capture, evil-twin, or cracking automation.

Pwnagotchi source reference cloned at: `/home/pi/src/pwnagotchi`

Pwnagotchi is GPLv3. Spac3-Gh0st includes adapted GPLv3 face/voice concepts and ships with a GPLv3 notice in `LICENSE-PWNAGOTCHI-NOTICE.md`.

## Launch

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

Original Pwnagotchi plugins are discovered but not executed automatically because many assume bettercap, monitor mode, deauth, handshakes, and/or online credential-upload workflows. Spac3-Gh0st uses native safe shims instead.
