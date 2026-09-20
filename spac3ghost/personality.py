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
    'GHOST': '(@-@)', 'RADAR': '(⊙_◎)', 'BT': '(⌁_⌁)', 'GPS': '(⌖_⌖)',
    'HOT': ['(°▃▃°)', '(>_<)', '(-_-")', '(🔥_🔥)'],
    'WARM': ['(>_<)', '(=_=;)', '(•_•;)', '(☼_☼)'],
    'COLD': ['(❄_❄)', '(⌐❄_❄)', '(=_=)'],
    'HUMID': ['(☁_☁)', '(=湿=)', '(~_~;)'],
    'DRY': ['(._.)', '(砂_砂)', '(=_=)'],
    'BRIGHT': ['(☼_☼)', '(⌐□_□)', '(⊙_⊙)'],
    'DARK': ['(⌐■_■)', '(■_■¬)', '(■‿■¬)'],
    'STORM': ['(ϟ_ϟ)', '(☂_☂)', '(⚆_⚆)', '(⊙_◎)'],
    'RAIN': ['(☂_☂)', '(•́_•̀)', '(☁‿☁)'],
    'SNOW': ['(❄‿❄)', '(❄_❄)', '(⌐❄_❄)'],
    'FOG': ['(░_░)', '(◌_◌)', '(=_=)'],
    'WIND': ['(≋_≋)', '(~_~)', '(⌁_⌁)'],
    'SOUND': ['(♪_♪)', '(♫‿♫)', '(•‿•)'],
    'MUTE': ['(…_…)', '(¬_¬)', '(-__-)'],
    'DAYDARK': ['(☼_■)', '(☀_□)', '(⌐□_☼)'],
    'NIGHT': ['(☾_☾)', '(☽_☽)', '(■_■¬)'],
    'NIGHTLIGHT': ['(☾_☼)', '(☽_☼)', '(⌐☾_☼)'],
    'MORNING': ['(☕_☕)', '(☼_☕)', '(◕_☼)'],
    'EVENING': ['(☾‿☼)', '(☽_☼)', '(•_☾)'],
    'ROOMCOOL': ['(⌐❄_□)', '(❄_□)', '(=_=)'],
    'ROOMWARM': ['(☼_☼)', '(=_=;)', '(•_•;)'],
    'NOISY': ['(ಠ_ಠ)', '(╬_╬)', '(♪_ಠ)'],
    'MOVEMENT': ['(◎_◎)', '(⚆_⚆)', '(⊙_⊙)'],
    'STAT': ['(✜_✜)', '(1_0)', '(⌁_✜)'],
    'ALERT': ['( ⚆_⚆)', '(☉_☉ )', '(@_@)', '(#__#)'],
    'BLUETOOTH': ['(⌁_⌁)', '(⌁‿⌁)', '(⌁_◎)'],
    'LOCATED': ['(⌖_⌖)', '(⌖‿⌖)', '(⌖_◎)'],
    'SCANNING': ['(⊙_◎)', '(◎_⊙)', '(⊙_⊙)'],
    'CURIOUS': ['(◕‿‿◕)', '( ⚆_⚆)', '(☉_☉ )', '(✜‿‿✜)', '(@-@)']
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

    def atmosphere(self, key: str, **fmt):
        defaults = {
            'daydark': ['Daylight outside, lights off inside. Not night — just cave mode.', 'It is daytime, but the room is dark. Indoor stealth, outdoor sun.'],
            'nightdark': ['Night outside and the room is dark. Classic ghost hours.', 'Actual night detected. The shadows have paperwork.'],
            'nightlight': ['Night outside but the lights are on. Cozy lab-after-hours mode.', 'Indoor photons at night. Someone made the cave civilized.'],
            'daylight': ['Day mood: {summary}, {temp_f}°F. Ambient context: {lux} lux inside.', 'The sky says day; room sensor says {lux} lux; both facts can coexist like adults.'],
            'morning': ['Morning mood. Context: {summary}, {temp_f}°F, room lux {lux}.', 'Morning face online; Wi‑Fi {wifi_count}, BT {bt_count}, LAN {lan_count}.'],
            'evening': ['Evening mood. Context: {summary}, {temp_f}°F, room lux {lux}.', 'Evening face selected; the lab lighting can do whatever dramatic nonsense it wants.'],
            'night_time': ['Night mode. Current context: {summary}, {temp_f}°F, room light {lux} lux.', 'Proper night mood. Sensors report {summary}; GPS {gps_used}/{gps_seen}; room lux {lux}.'],
            'ambient_dark': ['Lights are off in the room; outside/time mood stays {mood}.', 'Ambient light is low. The house went dim, not magically midnight.', 'Room lux is {lux}. Not changing the face mood — just noting the cave vibes.'],
            'ambient_bright': ['Lights are on / bright room: {lux} lux. Mood remains tied to time and weather.', 'Indoor photons are loud: {lux} lux. Very visible, very suspicious.'],
            'scanning_context': ['Scanning context: Wi‑Fi {wifi_count}, BT {bt_count}, LAN {lan_count}. The face keeps the broader mood.', 'Signal sweep in progress: {wifi_count} SSIDs, {bt_count} blue whispers, {lan_count} LAN hosts.'],
            'roomcool': ['Room feels cool at {temp_f}°F. Tiny sweater protocol.', 'Cabin temp low: {temp_f}°F. Elegant little chill.'],
            'roomwarm': ['Room is warm at {temp_f}°F. Comfortable, but I am watching it.', 'Cabin warmth noted: {temp_f}°F. The atmosphere is getting cozy.'],
            'noisy': ['Noise/activity detected: {level}. The room has opinions.', 'Audio/movement atmosphere is busy. Little lab is not quiet.'],
            'movement': ['Movement context detected. The face keeps the proper time/weather mood.', 'Motion cue logged. Something nudged the little shit.', 'Movement/tilt changed recently. Atmosphere updated, identity crisis avoided.'],
            'stats': ['Stats: Wi‑Fi {wifi_count}, BT {bt_count}, LAN {lan_count}, GPS {gps_used}/{gps_seen}, CPU {cpu_f}°F.', 'Telemetry brief: {wifi_count} SSIDs, {bt_count} Bluetooth, {lan_count} LAN, CPU {cpu_f}°F.'],
            'skyclear': ['Clear sky mood. Context: {temp_f}°F, room lux {lux}, GPS {gps_used}/{gps_seen}.', 'Sky clear. Ambient telemetry: Wi‑Fi {wifi_count}, BT {bt_count}, LAN {lan_count}.'],
        }
        return self.configured(key, defaults.get(key, ['Atmosphere changed.']), **fmt)

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
        # Pwnagotchi-ish: lively, twitchy, and non-repeating. The Settings
        # config remains the source of truth; this only changes how fast lists
        # are sampled.
        bucket = int(t // 2)
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



def _num(*values):
    for value in values:
        if isinstance(value, (int, float)):
            return value
    return None


def _weather_words(summary: str) -> set[str]:
    low = str(summary or '').lower()
    words = set()
    mapping = {
        'storm': ['storm', 'thunder', 'lightning'],
        'rain': ['rain', 'shower', 'drizzle'],
        'snow': ['snow', 'sleet', 'ice'],
        'fog': ['fog', 'mist', 'haze'],
        'wind': ['wind', 'gust', 'breezy'],
        'clear': ['clear', 'sunny'],
        'cloud': ['cloud', 'overcast'],
    }
    for key, needles in mapping.items():
        if any(n in low for n in needles):
            words.add(key)
    return words


def _parse_clock_minutes(value: Any) -> int | None:
    text = str(value or '').strip()
    if not text:
        return None
    parts = text.upper().replace('.', '').split()
    hm = parts[0] if parts else ''
    try:
        hour_s, minute_s = hm.split(':', 1)
        hour, minute = int(hour_s), int(minute_s[:2])
    except Exception:
        return None
    suffix = parts[1] if len(parts) > 1 else ''
    if suffix == 'PM' and hour != 12:
        hour += 12
    if suffix == 'AM' and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def _day_phase(weather: Dict[str, Any], now: float | None = None) -> str:
    t = time.localtime(time.time() if now is None else now)
    minute = t.tm_hour * 60 + t.tm_min
    sunrise = _parse_clock_minutes(weather.get('sunrise'))
    sunset = _parse_clock_minutes(weather.get('sunset'))
    if sunrise is None or sunset is None or sunrise == sunset:
        if 5 <= t.tm_hour < 11:
            return 'morning'
        if 11 <= t.tm_hour < 17:
            return 'day'
        if 17 <= t.tm_hour < 21:
            return 'evening'
        return 'night'
    if sunrise <= minute < sunrise + 120:
        return 'morning'
    if sunset - 90 <= minute < sunset + 60:
        return 'evening'
    if sunrise <= minute < sunset:
        return 'day'
    return 'night'


def _sound_level(status: Dict[str, Any], sensors: Dict[str, Any]) -> float | None:
    for bucket in (sensors.get('sound'), sensors.get('noise'), sensors.get('microphone'), status.get('sound')):
        if isinstance(bucket, dict):
            val = _num(bucket.get('db'), bucket.get('dB'), bucket.get('level'), bucket.get('percent'))
            if val is not None:
                return val
        elif isinstance(bucket, (int, float)):
            return bucket
    return None


def _normal_mood_name(phase: str, words: set[str], rng: random.Random) -> str:
    """Pick a normal companion mood that is not purely a weather icon."""
    if phase == 'morning':
        pool = ['morning', 'morning', 'curious']
    elif phase == 'evening':
        pool = ['evening', 'evening', 'curious']
    elif phase == 'night':
        pool = ['night', 'night', 'curious']
    elif 'clear' in words:
        pool = ['skyclear', 'curious', 'daylight']
    else:
        pool = ['daylight', 'curious', 'daylight']
    return rng.choice(pool)


def _mood_payload(name: str, now: float | None, salt: str) -> Dict[str, str]:
    table = {
        'stormwatch': ('storm', '#8b5cf6'),
        'rainwatch': ('rain', '#5ac8fa'),
        'snowghost': ('snow', '#5ac8fa'),
        'fogghost': ('fog', '#8e8e93'),
        'windwatch': ('wind', '#64d2ff'),
        'sunbaked': ('bright', '#ffbd2e'),
        'watching': ('scanning', '#27c93f'),
        'cloaked': ('dark', '#bf5af2'),
        'scanning': ('scanning', '#bf5af2'),
        'soundwave': ('sound', '#bf5af2'),
        'morning': ('morning', '#ffbd2e'),
        'evening': ('evening', '#bf5af2'),
        'night': ('night', '#bf5af2'),
        'skyclear': ('curious', '#27c93f'),
        'curious': ('curious', '#27c93f'),
        'daylight': ('bright', '#ffbd2e'),
    }
    face_key, color = table.get(name, ('curious', '#27c93f'))
    return {'name': name, 'face': _face(face_key, now, salt), 'color': color}


def choose_mood(status: Dict[str, Any], now: float | None = None) -> Dict[str, str]:
    cfg = load_config().get('mood', {})
    system = status.get('system', {}) if isinstance(status.get('system', {}), dict) else {}
    wifi = status.get('wifi', {}) if isinstance(status.get('wifi', {}), dict) else {}
    lan = status.get('lan', {}) if isinstance(status.get('lan', {}), dict) else {}
    bt = status.get('bluetooth', {}) if isinstance(status.get('bluetooth', {}), dict) else {}
    sensors = status.get('sensors', {}) if isinstance(status.get('sensors', {}), dict) else {}
    vision = status.get('vision', {}) if isinstance(status.get('vision', {}), dict) else {}
    vpn = status.get('vpn', {}) if isinstance(status.get('vpn', {}), dict) else {}
    controls = status.get('controls', {}) if isinstance(status.get('controls', {}), dict) else {}
    alert = status.get('alert', {}) if isinstance(status.get('alert', {}), dict) else {}
    salt = _status_salt(status)

    temp_c = _num(system.get('cpu_temp_c'))
    weather = sensors.get('weather', {}) if isinstance(sensors.get('weather', {}), dict) else {}
    weather_f = _num(weather.get('tempF'))
    words = _weather_words(str(weather.get('summary') or ''))
    phase = _day_phase(weather, now)

    # Critical host/security states can still override the face.
    if isinstance(temp_c, (int, float)) and temp_c >= cfg.get('hot_c', 75):
        return {'name': 'hot', 'face': _face('hot', now, salt), 'color': '#ff5f56'}
    if isinstance(temp_c, (int, float)) and temp_c >= cfg.get('warm_c', 65):
        return {'name': 'warm', 'face': _face('warm', now, salt), 'color': '#ffbd2e'}
    if alert.get('level') == 'RED' or wifi.get('new_count', 0) or lan.get('new_count', 0):
        return {'name': 'alert', 'face': _face('alert', now, salt), 'color': '#ffbd2e'}

    # Face mood is primarily time/major-mode. Ordinary weather is a flavor:
    # rain/storm/etc. should occasionally surface, then normal companion moods
    # should intertwine so the face does not become a weather-icon loop.
    t = time.time() if now is None else now
    hold_s = max(20, int(cfg.get('mood_hold_s', 45)))
    mood_bucket = int(t // hold_s)
    rng = random.Random(f'mood:{mood_bucket}:{phase}:{sorted(words)}:{round(weather_f or 0)}:{salt}')
    weather_moods = []
    if 'storm' in words:
        weather_moods.append('stormwatch')
    if 'rain' in words:
        weather_moods.append('rainwatch')
    if 'snow' in words or (isinstance(weather_f, (int, float)) and weather_f <= cfg.get('weather_cold_f', 35)):
        weather_moods.append('snowghost')
    if 'fog' in words:
        weather_moods.append('fogghost')
    if 'wind' in words:
        weather_moods.append('windwatch')
    if isinstance(weather_f, (int, float)) and weather_f >= cfg.get('weather_hot_f', 88):
        weather_moods.append('sunbaked')

    if weather_moods and rng.random() < float(cfg.get('weather_face_weight', 0.28)):
        return _mood_payload(rng.choice(weather_moods), now, salt)

    if vision.get('enabled'):
        return _mood_payload('watching', now, salt)
    if vpn.get('active') or vpn.get('gui_running'):
        return _mood_payload('cloaked', now, salt)
    if wifi.get('scan_active') or lan.get('scan_active') or bt.get('scan_active'):
        return _mood_payload('scanning', now, salt)
    if controls.get('sound') or status.get('sound_enabled'):
        return _mood_payload('soundwave', now, salt)

    return _mood_payload(_normal_mood_name(phase, words, rng), now, salt)

def _ambient_phrase(voice: Spac3Voice, status: Dict[str, Any], mood: str, temp: float | None) -> tuple[str, str] | None:
    sensors = status.get('sensors', {}) if isinstance(status.get('sensors', {}), dict) else {}
    wifi = status.get('wifi', {}) if isinstance(status.get('wifi', {}), dict) else {}
    lan = status.get('lan', {}) if isinstance(status.get('lan', {}), dict) else {}
    bt = status.get('bluetooth', {}) if isinstance(status.get('bluetooth', {}), dict) else {}
    weather = sensors.get('weather', {}) if isinstance(sensors.get('weather', {}), dict) else {}
    light = sensors.get('light', {}) if isinstance(sensors.get('light', {}), dict) else {}
    indoor = sensors.get('indoor', {}) if isinstance(sensors.get('indoor', {}), dict) else {}
    gps = sensors.get('gps', {}) if isinstance(sensors.get('gps', {}), dict) else {}
    tilt = sensors.get('tilt_event', {}) if isinstance(sensors.get('tilt_event', {}), dict) else {}
    lux = _num(light.get('lux'))
    noise = _sound_level(status, sensors)
    phase = _day_phase(weather)
    wifi_count = len(wifi.get('networks', []) or [])
    bt_count = len(bt.get('devices', []) or [])
    lan_count = len(lan.get('devices', []) or [])
    fmt = {
        'summary': weather.get('summary') or 'unknown', 'temp_f': weather.get('tempF') if weather.get('tempF') is not None else '?',
        'lux': lux if lux is not None else '?', 'level': noise if noise is not None else 'detected',
        'wifi_count': wifi_count, 'bt_count': bt_count, 'lan_count': lan_count,
        'gps_used': gps.get('satellitesUsed') or 0, 'gps_seen': gps.get('satellitesVisible') or 0,
        'cpu_f': temp if isinstance(temp, (int, float)) else '?', 'humidity': indoor.get('humidity', '?'), 'mood': mood,
    }
    if wifi.get('scan_active') or lan.get('scan_active') or bt.get('scan_active'):
        return voice.atmosphere('scanning_context', **fmt), 'scan'
    if tilt.get('fast') or sensors.get('motion') or sensors.get('movement'):
        return voice.atmosphere('movement', **fmt), 'movement'
    if isinstance(noise, (int, float)) and noise >= voice.config.get('mood', {}).get('noise_active_level', 65):
        return voice.atmosphere('noisy', **fmt), 'sound'
    if isinstance(lux, (int, float)) and lux <= voice.config.get('mood', {}).get('dark_lux', 10):
        return voice.atmosphere('ambient_dark', **fmt), 'light'
    if isinstance(lux, (int, float)) and lux >= voice.config.get('mood', {}).get('bright_lux', 250):
        return voice.atmosphere('ambient_bright', **fmt), 'light'
    if wifi_count or bt_count or lan_count:
        return voice.atmosphere('stats', **fmt), 'stats'
    return None

def event_from_status(status: Dict[str, Any]) -> Dict[str, Any]:
    voice = Spac3Voice()
    system = status.get('system', {})
    sensors = status.get('sensors', {}) if isinstance(status, dict) else {}
    temp = system.get('cpu_temp_f')
    if temp is None and isinstance(system.get('cpu_temp_c'), (int, float)):
        temp = system.get('cpu_temp_c') * 9 / 5 + 32
    mood = choose_mood(status).get('name')

    # The face/mood shows time/weather/major mode; the phrase reports what is happening now.
    ambient = _ambient_phrase(voice, status, mood, temp)
    if ambient and mood not in ('hot', 'warm', 'alert'):
        text, kind = ambient
    elif mood == 'hot' and isinstance(temp, (int, float)):
        text, kind = voice.hot(temp), 'thermal'
    elif mood == 'warm' and isinstance(temp, (int, float)):
        text, kind = voice.warm(temp), 'thermal'
    elif mood in ('stormwatch', 'rainwatch', 'snowghost', 'fogghost', 'windwatch', 'sunbaked'):
        w = sensors.get('weather', {})
        text, kind = voice.weather(w.get('summary', 'unknown'), w.get('tempF')), 'weather'
    elif mood in ('morning', 'evening', 'night', 'daylight', 'skyclear'):
        w = sensors.get('weather', {}) if isinstance(sensors, dict) else {}
        text, kind = voice.atmosphere(mood if mood != 'night' else 'night_time',
            summary=w.get('summary') or 'unknown', temp_f=w.get('tempF') if w.get('tempF') is not None else '?',
            lux=(sensors.get('light') or {}).get('lux') if isinstance(sensors.get('light', {}), dict) else '?',
            level=_sound_level(status, sensors) or 'detected',
            wifi_count=len(status.get('wifi', {}).get('networks', []) or []),
            bt_count=len(status.get('bluetooth', {}).get('devices', []) or []),
            lan_count=len(status.get('lan', {}).get('devices', []) or []),
            gps_used=(sensors.get('gps') or {}).get('satellitesUsed') or 0 if isinstance(sensors.get('gps', {}), dict) else 0,
            gps_seen=(sensors.get('gps') or {}).get('satellitesVisible') or 0 if isinstance(sensors.get('gps', {}), dict) else 0,
            cpu_f=temp if isinstance(temp, (int, float)) else '?',
        ), 'atmosphere'
    elif mood == 'soundwave':
        text, kind = voice.configured('soundwave', ['Sound is on. I have tiny nightclub privileges.']), 'sound'
    elif mood == 'watching':
        text, kind = voice.configured('watching', ['Vision is awake. One careful eye open.']), 'vision'
    elif mood == 'cloaked':
        text, kind = voice.configured('cloaked', ['Cloak vibes detected. Packets wearing fake mustaches.']), 'vpn'
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

