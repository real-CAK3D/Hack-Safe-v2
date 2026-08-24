"""Spac3-Gh0st personality engine.

Face constants are adapted from Pwnagotchi's GPLv3 `pwnagotchi/ui/faces.py`.
Voice style is inspired by Pwnagotchi's event-driven `voice.py`, rewritten for
safe local recon/defensive companion events.
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict

from .config import load_config

FACE = {
    'LOOK_R': '( ⚆_⚆)', 'LOOK_L': '(☉_☉ )', 'LOOK_R_HAPPY': '( ◕‿◕)', 'LOOK_L_HAPPY': '(◕‿◕ )',
    'SLEEP': '(⇀‿‿↼)', 'SLEEP2': '(≖‿‿≖)', 'AWAKE': '(◕‿‿◕)', 'BORED': '(-__-)',
    'INTENSE': '(°▃▃°)', 'COOL': '(⌐■_■)', 'HAPPY': '(•‿‿•)', 'GRATEFUL': '(^‿‿^)',
    'EXCITED': '(ᵔ◡◡ᵔ)', 'MOTIVATED': '(☼‿‿☼)', 'DEMOTIVATED': '(≖__≖)', 'SMART': '(✜‿‿✜)',
    'LONELY': '(ب__ب)', 'SAD': '(╥☁╥ )', 'ANGRY': "(-_-')", 'FRIEND': '(♥‿‿♥)',
    'BROKEN': '(☓‿‿☓)', 'DEBUG': '(#__#)', 'UPLOAD': '(1__0)', 'UPLOAD1': '(1__1)', 'UPLOAD2': '(0__1)',
    'GHOST': '(@-@)', 'RADAR': '(⊙_◎)', 'BT': '(⌁_⌁)', 'GPS': '(⌖_⌖)'
}

FACE_MEMORY: Dict[str, Any] = {'last': {}}


def merged_faces() -> Dict[str, Any]:
    faces = dict(FACE)
    faces.update({k.upper(): v for k, v in load_config().get('faces', {}).items() if isinstance(v, (str, list))})
    return faces


class Spac3Voice:
    def __init__(self, seed: int | None = None):
        self.random = random.Random(seed)
        self.config = load_config()

    def pick(self, options):
        return self.random.choice(list(options))

    def configured(self, key: str, fallback, **fmt):
        phrases = self.config.get('phrases', {}).get(key) or fallback
        text = self.pick(phrases)
        try:
            return text.format(**fmt)
        except Exception:
            return text

    def starting(self):
        return self.configured('starting', [
            'Spac3-Gh0st online. I am awake in the wires.',
            'Boot complete. The little machine has opinions now.',
            'New night, new signals. I can feel the air humming.',
        ])

    def idle(self):
        return self.configured('idle', [
            'I am quiet, not asleep.',
            'Still here. Still breathing in packets.',
            'Wake me when the LEDs start acting suspicious.',
        ])

    def wifi_scan(self, count: int):
        return self.configured('wifi_scan', [
            '{count} Wi-Fi beacons brushed past my antenna.',
            'Radio sweep complete. {count} SSIDs blinked.',
            'I tasted {count} access points in the air.',
            'Wi-Fi sweep saw {count} networks. Nosy little lights.',
        ], count=count)

    def bluetooth_scan(self, count: int):
        return self.configured('bluetooth_scan', [
            'Bluetooth sweep: {count} nearby signals.',
            'Short-range sweep counted {count} devices.',
            'The blue ether coughed up {count} names.',
        ], count=count)

    def lan_scan(self, count: int):
        return self.configured('lan_scan', [
            'LAN sweep saw {count} hosts.',
            '{count} machines share our deck.',
            'Network neighborhood mapped: {count} nodes.',
        ], count=count)

    def new_thing(self, kind: str, name: str):
        return self.configured('new_thing', [
            'New {kind}: {name}. Curious.',
            'Something new appeared in {kind}: {name}.',
            "I don't remember this {kind}: {name}.",
        ], kind=kind, name=name)

    def gps(self, label: str, used: int = 0):
        if 'NO' in str(label).upper() or used == 0:
            return self.configured('gps_no_fix', [
                'GPS has no fix. I am drifting blind.',
                'No location lock. The sky is ignoring me.',
                'Satellites visible, trust unavailable.',
            ])
        return self.configured('gps_fix', [
            'GPS {label}. {used} satellites trust us.',
            'GPS found me on the planet again.',
            'Location locked. I know where my tiny body is.',
        ], label=label, used=used)

    def hot(self, temp):
        return self.configured('hot', ['CPU is spicy at {temp:.1f}°F.', 'Thermals are haunted.', 'I am sweating electrons.'], temp=temp)

    def warm(self, temp):
        return self.configured('warm', ['I am getting warm: {temp:.1f}°F.'], temp=temp)

    def tilted(self):
        return self.configured('tilted', ['Whoa. The deck just lurched.'])

    def weather(self, summary: str, temp_f: float | None):
        low = str(summary or '').lower()
        if any(word in low for word in ['storm', 'rain', 'snow', 'thunder', 'shower']):
            return self.configured('storm', ['Weather looks moody: {summary}.'], summary=summary)
        cfg = self.config.get('mood', {})
        if isinstance(temp_f, (int, float)) and temp_f >= cfg.get('weather_hot_f', 88):
            return self.configured('weather_hot', ['Outside is hot: {temp_f:.1f}°F.'], temp_f=temp_f)
        if isinstance(temp_f, (int, float)) and temp_f <= cfg.get('weather_cold_f', 35):
            return self.configured('weather_cold', ['Outside is cold: {temp_f:.1f}°F.'], temp_f=temp_f)
        return self.configured('weather_clear', ['Weather says {summary}.', 'Sky scan complete.'], summary=summary or 'unknown')

    def light(self, lux):
        cfg = self.config.get('mood', {})
        if isinstance(lux, (int, float)) and lux <= cfg.get('dark_lux', 10):
            return self.configured('dark', ['Low light. Stealth mode enhanced.'])
        if isinstance(lux, (int, float)) and lux >= cfg.get('bright_lux', 250):
            return self.configured('bright', ['Bright light detected. No hiding now.'])
        return self.configured('light_normal', ['Ambient light normal.', 'Light levels acceptable.'])

    def service(self, name: str, active: bool):
        if not active:
            return self.configured('service_down', ['{service} went dark.'], service=name)
        return self.configured('service_up', ['{service} is awake.', 'Service check: {service} green.'], service=name)

    def settings_saved(self):
        return self.configured('settings_saved', ['Settings saved. I rearranged my brain and stayed alive.'])

    def sensors_refreshed(self):
        return self.configured('sensors_refreshed', ['Sensors refreshed. Reality pinged back.'])

    def vision_toggle(self, enabled: bool):
        key = 'vision_on' if enabled else 'vision_off'
        fallback = ['Vision armed. I opened one careful eye.'] if enabled else ['Vision disarmed. Eye closed.']
        return self.configured(key, fallback)

    def vpn_result(self, action: str = 'toggle'):
        return self.configured('vpn', ['VPN {action}. The packets put on fake mustaches.'], action=action)

    def service_result(self, label: str, action: str, active_text: str):
        return self.configured('service_toggle', ['{service} {action} -> {state}.'], service=label, action=action, state=active_text)

    def yolo_result(self, labels=None, error: str = ''):
        labels = [str(x) for x in (labels or []) if x]
        if labels:
            return self.configured('yolo_seen', ['YOLO saw {labels}. The eye has receipts.'], labels=', '.join(labels[:4]))
        return self.configured('yolo_empty', ['YOLO saw nothing obvious. Suspiciously boring.', 'No detections. Clean room or sneaky room?'], error=error or 'nothing obvious')

    def chatter(self, status: Dict[str, Any]):
        wifi_count = len(status.get('wifi', {}).get('networks', []) or [])
        bt_count = len(status.get('bluetooth', {}).get('devices', []) or [])
        lan_count = len(status.get('lan', {}).get('devices', []) or [])
        plugin_count = len([p for p in status.get('native_plugins', []) if p.get('loaded')])
        # Vision being armed is already visible in controls/events. Do not spam the chatter feed every refresh.
        if status.get('vpn', {}).get('active'):
            return self.configured('vpn', ['VPN cloak is up.'])
        if bt_count and self.random.random() < 0.25:
            return self.configured('bluetooth_chatter', ['Bluetooth ether shows {bt_count} devices.'], bt_count=bt_count)
        if plugin_count and self.random.random() < 0.25:
            return self.configured('plugin_chatter', ['{plugin_count} plugins are awake and behaving mostly.'], plugin_count=plugin_count, bt_count=bt_count, wifi_count=wifi_count, lan_count=lan_count)
        # Rare prank interruption so the feed feels alive rather than like a loop.
        if self.random.random() < 0.12:
            return self.configured('pranks', ['Woah, look behind you... syke, gotcha.'])
        return self.configured(
            'network_chatter',
            self.config.get('phrases', {}).get('chatter') or ['Still here. Still watching.'],
            wifi_count=wifi_count,
            bt_count=bt_count,
            lan_count=lan_count,
            plugin_count=plugin_count,
        )


def _face(name: str, now: float | None = None, salt: str = '') -> str:
    value = merged_faces().get(name.upper(), FACE.get(name.upper(), '(@-@)'))
    if isinstance(value, list) and value:
        t = time.time() if now is None else now
        # Pwnagotchi-ish: not a slideshow. Pick a mood face from a seeded,
        # jittery bucket and avoid repeating the last face for that mood.
        bucket = int(t // 3)
        seed = f'{name}:{bucket}:{salt}:{int(t * 1000) % 997}'
        options = [str(v) for v in value]
        rng = random.Random(seed)
        choice = rng.choice(options)
        last = FACE_MEMORY.setdefault('last', {}).get(name)
        if len(options) > 1 and choice == last:
            choice = rng.choice([v for v in options if v != last])
        FACE_MEMORY.setdefault('last', {})[name] = choice
        return choice
    return str(value)


def _status_salt(status: Dict[str, Any]) -> str:
    sensors = status.get('sensors', {}) if isinstance(status.get('sensors', {}), dict) else {}
    gps = sensors.get('gps', {}) if isinstance(sensors.get('gps', {}), dict) else {}
    return '|'.join([
        str(len(status.get('wifi', {}).get('networks', []) or [])),
        str(status.get('wifi', {}).get('new_count', 0)),
        str(len(status.get('bluetooth', {}).get('devices', []) or [])),
        str(status.get('bluetooth', {}).get('new_count', 0)),
        str(len(status.get('lan', {}).get('devices', []) or [])),
        str(status.get('lan', {}).get('new_count', 0)),
        str(gps.get('modeLabel', '')),
        str(status.get('vision', {}).get('enabled', False)),
        str(status.get('vpn', {}).get('active', False)),
    ])


def choose_mood(status: Dict[str, Any], now: float | None = None) -> Dict[str, str]:
    cfg = load_config().get('mood', {})
    system = status.get('system', {})
    wifi = status.get('wifi', {})
    lan = status.get('lan', {})
    bt = status.get('bluetooth', {})
    sensors = status.get('sensors', {}) if isinstance(status.get('sensors', {}), dict) else {}
    vision = status.get('vision', {}) if isinstance(status.get('vision', {}), dict) else {}
    vpn = status.get('vpn', {}) if isinstance(status.get('vpn', {}), dict) else {}
    salt = _status_salt(status)
    temp = system.get('cpu_temp_c')
    indoor = sensors.get('indoor', {}) if isinstance(sensors.get('indoor', {}), dict) else {}
    indoor_f = indoor.get('tempF')
    light = sensors.get('light', {})
    lux = light.get('lux')
    # Face color policy for Hack-Safe: green most of the time, purple at night,
    # yellow/red for warm/hot thermals, blue for cold. Vision should not hijack it.
    if isinstance(temp, (int, float)) and temp >= cfg.get('hot_c', 75):
        return {'name': 'hot', 'face': _face('hot', now, salt), 'color': '#ff5f56'}
    if isinstance(temp, (int, float)) and temp >= cfg.get('warm_c', 65):
        return {'name': 'warm', 'face': _face('warm', now, salt), 'color': '#ffbd2e'}
    if (isinstance(temp, (int, float)) and temp < cfg.get('cold_c', 40)) or (isinstance(indoor_f, (int, float)) and indoor_f <= cfg.get('indoor_cold_f', 60)):
        return {'name': 'cold', 'face': _face('cold', now, salt), 'color': '#5ac8fa'}
    if isinstance(lux, (int, float)) and lux <= cfg.get('dark_lux', 10):
        return {'name': 'night', 'face': _face('dark', now, salt), 'color': '#bf5af2'}
    tilt_event = sensors.get('tilt_event', {})
    if tilt_event.get('fast') and tilt_event.get('orientation') == 'TILTED':
        return {'name': 'tilted', 'face': _face('tilted', now, salt), 'color': '#27c93f'}
    weather = sensors.get('weather', {})
    summary = str(weather.get('summary') or '').lower()
    if any(word in summary for word in ['storm', 'rain', 'snow', 'thunder', 'shower']):
        return {'name': 'stormwatch', 'face': _face('storm', now, salt), 'color': '#27c93f'}
    if wifi.get('new_count', 0) or lan.get('new_count', 0):
        return {'name': 'alert', 'face': _face('alert', now, salt), 'color': '#ffbd2e'}
    if bt.get('new_count', 0):
        return {'name': 'bluetooth', 'face': _face('bluetooth', now, salt), 'color': '#27c93f'}
    gps = sensors.get('gps', {})
    if gps.get('fixed'):
        return {'name': 'located', 'face': _face('located', now, salt), 'color': '#27c93f'}
    if not wifi.get('connected', True) and not wifi.get('networks') and not lan.get('devices') and not bt.get('devices'):
        return {'name': 'lonely', 'face': _face('LONELY', now, salt), 'color': '#8e8e93'}
    if wifi.get('scan_active') or lan.get('scan_active') or bt.get('scan_active'):
        return {'name': 'scanning', 'face': _face('scanning', now, salt), 'color': '#bf5af2'}
    return {'name': 'curious', 'face': _face('curious', now, salt), 'color': '#27c93f'}


def event_from_status(status: Dict[str, Any]) -> Dict[str, Any]:
    voice = Spac3Voice()
    system = status.get('system', {})
    sensors = status.get('sensors', {}) if isinstance(status, dict) else {}
    temp = system.get('cpu_temp_f')
    if temp is None and isinstance(system.get('cpu_temp_c'), (int, float)):
        temp = system.get('cpu_temp_c') * 9 / 5 + 32
    mood = choose_mood(status).get('name')
    if mood == 'hot' and isinstance(temp, (int, float)):
        text, kind = voice.hot(temp), 'thermal'
    elif mood == 'warm' and isinstance(temp, (int, float)):
        text, kind = voice.warm(temp), 'thermal'
    elif mood == 'tilted':
        text, kind = voice.tilted(), 'tilt'
    elif mood in ('stormwatch',):
        w = sensors.get('weather', {})
        text, kind = voice.weather(w.get('summary', 'unknown'), w.get('tempF')), 'weather'
    elif mood == 'night':
        text, kind = voice.light(sensors.get('light', {}).get('lux')), 'light'
    else:
        down = [name for name, info in status.get('services', {}).items() if isinstance(info, dict) and not info.get('active')]
        if down:
            text, kind = voice.service(down[0], False), 'service'
        else:
            gps = sensors.get('gps', {}) if isinstance(sensors, dict) else {}
            if gps:
                text, kind = voice.gps(gps.get('modeLabel', 'NO FIX'), gps.get('satellitesUsed') or 0), 'gps'
            else:
                wifi = status.get('wifi', {})
                text, kind = voice.wifi_scan(len(wifi.get('networks') or [])) if 'networks' in wifi else voice.idle(), 'wifi'
    return {'ts': int(time.time()), 'kind': kind, 'text': text}
