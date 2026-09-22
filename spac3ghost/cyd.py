from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

from .paths import DATA_DIR

STATE_PATH = DATA_DIR / 'cyd_buddy.json'
SETTINGS_PATH = DATA_DIR / 'cyd_buddy_settings.json'
LEASE_PATHS = (
    Path('/var/lib/NetworkManager/dnsmasq-wlan1.leases'),
    Path('/var/lib/NetworkManager/dnsmasq-Wu-Tang LAN.leases'),
    Path('/var/lib/misc/dnsmasq.leases'),
)
SSID = 'Wu-Tang LAN'
HOTSPOT_IP = '10.42.7.1'
TELEMETRY_PATH = '/api/cyd/telemetry'
HEARTBEAT_PATH = '/api/cyd/heartbeat'

MENU_DEFS = [
    {'id': 'home', 'label': 'Home Face', 'hint': 'Return Buddy to the normal face / dock screen.'},
    {'id': 'display', 'label': 'Display', 'hint': 'Brightness, sleep, and visual comfort.'},
    {'id': 'face', 'label': 'Face / Mood', 'hint': 'Face style, mood, and personality panel.'},
    {'id': 'phrases', 'label': 'Voice / Phrases', 'hint': 'Phrase pack, scroll speed, and current voice line.'},
    {'id': 'wifi', 'label': 'Wi-Fi / Dock', 'hint': 'Dock network, heartbeat, and hotspot details.'},
    {'id': 'memory', 'label': 'Memory / Learning', 'hint': 'Learning state, favorite things, and memory bank.'},
    {'id': 'firmware', 'label': 'Firmware / Status', 'hint': 'Firmware version, uptime, logs, and diagnostics.'},
    {'id': 'advanced', 'label': 'Advanced', 'hint': 'Careful diagnostics only; no secrets are shown.'},
]
MENU_IDS = {m['id'] for m in MENU_DEFS}
DEFAULT_SETTINGS = {
    'active_menu': 'home',
    'display': {'brightness': 70, 'sleep_s': 60, 'theme': 'matrix'},
    'face': {'mood': 'auto', 'animation': 'auto', 'personality': 'chill'},
    'phrases': {'scroll_ms': 80, 'sd_lookup': False},
    'advanced': {'diagnostics': False},
    'pending_command': None,
    'updated_at': 0,
}

EVENT_PHRASES = {
    'wifi_new': [
        'New Wi-Fi name in the air. Somebody brought a new little radio blip.',
        'Fresh network spotted. I am adding it to the neighborhood gossip map.',
        'New Wi-Fi nearby. My tiny antenna instincts are twitching.',
        'I see a new network in the area. Noted, judged, archived.',
        'A new SSID just wandered in. I have questions and zero chill.',
        'New Wi-Fi signature detected. The walls are talking again.',
        'Another network appeared. I grow stronger on broadcast crumbs.',
        'Fresh Wi-Fi contact. The local air is getting crowded.',
        'New network found. I am politely suspicious.',
        'SSID I have not seen before. Delicious little signal snack.',
    ],
    'bluetooth_new': [
        'New Bluetooth name nearby. Armor up, little buddy mode engaged.',
        'Bluetooth stranger detected. I am side-eyeing the air.',
        'A new Bluetooth device just whispered hello.',
        'Fresh Bluetooth contact. Pocket technology is being weird again.',
        'New Bluetooth name logged. My invisible guest list got longer.',
    ],
    'lan_new': [
        'New LAN contact showed up. The house network has company.',
        'A new local device joined the party. I am watching politely.',
        'LAN neighbor detected. Somebody is awake on the wire.',
        'Fresh local network contact. I put it on the map.',
        'New device on the LAN. The dock has gossip.',
    ],
    'mesh_new': [
        'New mesh node heard. The long-range whisper net is waking up.',
        'LoRa contact detected. Tiny radios, big dramatic energy.',
        'Mesh activity in the air. I love a good distant beep.',
        'A mesh node just checked in. The horizon has opinions.',
        'New Meshtastic node heard. Signal meter filled.',
    ],
    'mesh_message': [
        'Mesh message received. Somebody out there had something to say.',
        'LoRa message landed. The air mail is working.',
        'New mesh message. Long-range gossip acquired.',
        'The mesh just spoke. I am listening.',
        'Message from the radio net. Noted with tiny ceremony.',
    ],
    'alert': [
        'Alert level changed. I am awake and making the serious eyes.',
        'Spac3-Gh0st raised an alert. I am paying attention now.',
        'Status changed upstairs. I am switching from vibes to watch mode.',
        'Something got spicy on the dock. I am monitoring it.',
        'Alert bump detected. My pixels are no longer loafing.',
    ],
}


def _now() -> int:
    return int(time.time())


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp.replace(path)


def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in (updates or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except Exception:
        return default


def _settings_state() -> Dict[str, Any]:
    saved = _read_json(SETTINGS_PATH, {})
    if not isinstance(saved, dict):
        saved = {}
    merged = _deep_merge(DEFAULT_SETTINGS, saved)
    active = str(merged.get('active_menu') or 'home')
    if active not in MENU_IDS:
        active = 'home'
    merged['active_menu'] = active
    merged['menus'] = MENU_DEFS
    return merged


def _save_settings(state: Dict[str, Any]) -> Dict[str, Any]:
    persisted = {k: v for k, v in state.items() if k != 'menus'}
    persisted['updated_at'] = _now()
    _write_json(SETTINGS_PATH, persisted)
    return _settings_state()


def cyd_settings() -> Dict[str, Any]:
    status = cyd_status(include_settings=False)
    settings = _settings_state()
    settings['ok'] = True
    settings['connected'] = bool(status.get('connected'))
    settings['buddy'] = {k: status.get(k) for k in ('name', 'ip', 'firmware', 'dock_label', 'heartbeat_recent')}
    return settings


def update_cyd_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = payload or {}
    status = cyd_status(include_settings=False)
    if not status.get('connected'):
        return {'ok': False, 'error': 'CYD Buddy is not docked/connected; settings command not sent.', 'connected': False}
    state = _settings_state()
    action = str(payload.get('action') or 'open_menu').strip().lower()
    menu = str(payload.get('menu') or state.get('active_menu') or 'home').strip().lower()
    if menu not in MENU_IDS:
        return {'ok': False, 'error': f'unknown CYD menu: {menu}', 'menus': MENU_DEFS}
    values = payload.get('values') if isinstance(payload.get('values'), dict) else {}
    if action in ('open_menu', 'menu'):
        state['active_menu'] = menu
    elif action in ('save', 'settings'):
        display = values.get('display') if isinstance(values.get('display'), dict) else {}
        face = values.get('face') if isinstance(values.get('face'), dict) else {}
        phrases = values.get('phrases') if isinstance(values.get('phrases'), dict) else {}
        advanced = values.get('advanced') if isinstance(values.get('advanced'), dict) else {}
        state['display'] = {
            'brightness': _clamp_int(display.get('brightness'), 5, 100, state.get('display', {}).get('brightness', 70)),
            'sleep_s': _clamp_int(display.get('sleep_s'), 0, 3600, state.get('display', {}).get('sleep_s', 60)),
            'theme': str(display.get('theme') or state.get('display', {}).get('theme') or 'matrix')[:32],
        }
        state['face'] = {
            'mood': str(face.get('mood') or state.get('face', {}).get('mood') or 'auto')[:32],
            'animation': str(face.get('animation') or state.get('face', {}).get('animation') or 'auto')[:32],
            'personality': str(face.get('personality') or state.get('face', {}).get('personality') or 'chill')[:32],
        }
        state['phrases'] = {
            'scroll_ms': _clamp_int(phrases.get('scroll_ms'), 20, 500, state.get('phrases', {}).get('scroll_ms', 80)),
            'sd_lookup': bool(phrases.get('sd_lookup', state.get('phrases', {}).get('sd_lookup', False))),
        }
        state['advanced'] = {'diagnostics': bool(advanced.get('diagnostics', state.get('advanced', {}).get('diagnostics', False)))}
    else:
        return {'ok': False, 'error': f'unsupported CYD settings action: {action}'}
    state['pending_command'] = {
        'id': f'cyd-{_now()}',
        'action': action,
        'menu': menu,
        'values': values if action in ('save', 'settings') else {},
        'created_at': _now(),
    }
    saved = _save_settings(state)
    saved['ok'] = True
    saved['connected'] = True
    return saved


def _event_phrase(kind: str, seed: int = 0) -> str:
    choices = EVENT_PHRASES.get(kind) or []
    if not choices:
        return ''
    return choices[abs(int(seed or time.time())) % len(choices)]


def _buddy_event_from_status(status: Dict[str, Any]) -> Dict[str, Any]:
    wifi = status.get('wifi') or {}
    bt = status.get('bluetooth') or {}
    lan = status.get('lan') or {}
    mesh = status.get('meshtastic') or {}
    alert = status.get('alert') or {}
    events = []
    for kind, label, count in (
        ('wifi_new', 'new Wi-Fi network', int(wifi.get('new_count') or 0)),
        ('bluetooth_new', 'new Bluetooth device', int(bt.get('new_count') or 0)),
        ('lan_new', 'new LAN device', int(lan.get('new_count') or 0)),
    ):
        if count > 0:
            events.append({'kind': kind, 'count': count, 'label': label})
    mesh_new = int(mesh.get('new_count') or 0)
    if mesh_new > 0:
        events.append({'kind': 'mesh_new', 'count': mesh_new, 'label': 'new mesh node'})
    if mesh.get('last_message'):
        events.append({'kind': 'mesh_message', 'count': 1, 'label': 'mesh message'})
    score = int(alert.get('score') or 0)
    if score >= 35:
        events.append({'kind': 'alert', 'count': score, 'label': str(alert.get('level') or 'alert')})
    if not events:
        return {'kind': '', 'text': '', 'count': 0}
    event = events[0]
    count = int(event.get('count') or 0)
    text = _event_phrase(str(event.get('kind') or ''), count + int(status.get('time') or 0))
    return {'kind': event.get('kind'), 'text': text, 'count': count, 'label': event.get('label')}


def _run(args: list[str], timeout: float = 1.5) -> str:
    try:
        cp = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
        return (cp.stdout or cp.stderr or '').strip()
    except Exception:
        return ''


def _connection_state() -> Dict[str, Any]:
    out = _run(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'])
    active = False
    device = ''
    for line in out.splitlines():
        parts = line.split(':')
        if len(parts) >= 3 and parts[0] == SSID:
            active = True
            device = parts[2]
            break
    dev = _run(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'dev', 'status'])
    wlan1_state = ''
    for line in dev.splitlines():
        parts = line.split(':')
        if parts and parts[0] == 'wlan1':
            wlan1_state = ':'.join(parts[2:])
            break
    return {'ssid': SSID, 'ip': HOTSPOT_IP, 'active': active, 'device': device or ('wlan1' if active else ''), 'wlan1_state': wlan1_state}


def _buddy_reachable(ip: str) -> bool:
    ip = str(ip or '').strip()
    if not ip.startswith('10.42.7.'):
        return False
    neigh = _run(['ip', 'neigh', 'show', ip], timeout=1.0).lower()
    if any(state in neigh for state in ('reachable', 'stale', 'delay', 'probe')):
        return True
    # Last-ditch bounded ping: only for the known CYD hotspot subnet, so a docked
    # Buddy can still expose controls even if its firmware heartbeat is stale.
    try:
        cp = subprocess.run(['ping', '-c', '1', '-W', '1', ip], text=True, capture_output=True, timeout=2)
        return cp.returncode == 0
    except Exception:
        return False


def _leases() -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    seen = set()
    for path in LEASE_PATHS:
        try:
            text = path.read_text()
        except Exception:
            continue
        for line in text.splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            expiry, mac, ip = parts[:3]
            name = parts[3] if len(parts) > 3 and parts[3] != '*' else ''
            key = (mac.lower(), ip)
            if key in seen:
                continue
            seen.add(key)
            try:
                exp = int(expiry)
            except ValueError:
                exp = 0
            rows.append({'mac': mac.lower(), 'ip': ip, 'name': name, 'expires_at': exp, 'lease_file': str(path), 'active': exp == 0 or exp > _now()})
    return rows


def record_heartbeat(payload: Dict[str, Any], client_ip: str = '') -> Dict[str, Any]:
    state = _read_json(STATE_PATH, {}) if isinstance(_read_json(STATE_PATH, {}), dict) else {}
    now = _now()
    raw = {k: v for k, v in payload.items() if k not in {'ip'}}
    buddy = {
        'last_seen': now,
        'ip': client_ip or payload.get('ip') or state.get('ip') or '',
        'name': str(payload.get('name') or payload.get('device') or state.get('name') or 'CYD Buddy'),
        'firmware': str(payload.get('firmware') or state.get('firmware') or ''),
        'face': str(payload.get('face') or state.get('face') or ''),
        'mood': str(payload.get('mood') or state.get('mood') or ''),
        'battery': payload.get('battery', state.get('battery')),
        'message': str(payload.get('message') or state.get('message') or ''),
        'stats': payload.get('stats') or state.get('stats') or {},
        'interactions': payload.get('interactions') or state.get('interactions') or {},
        'learning': payload.get('learning') or state.get('learning') or {},
        'memory': payload.get('memory') or state.get('memory') or {},
        'phrases': payload.get('phrases') or state.get('phrases') or {},
        'lifecycle': payload.get('lifecycle') or state.get('lifecycle') or {},
        'ai_state': payload.get('ai_state') or state.get('ai_state') or {},
        'raw': raw,
    }
    _write_json(STATE_PATH, buddy)
    if payload.get('settings_ack') or payload.get('command_ack'):
        settings = _settings_state()
        settings['last_ack'] = payload.get('settings_ack') or payload.get('command_ack')
        settings['pending_command'] = None
        _save_settings(settings)
    return {'ok': True, 'buddy': buddy, 'settings': _settings_state()}


def cyd_status(include_settings: bool = True) -> Dict[str, Any]:
    state = _read_json(STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}
    leases = _leases()
    now = _now()
    recent = bool(state.get('last_seen') and now - int(state.get('last_seen') or 0) <= 45)
    active_leases = [l for l in leases if l.get('active')]
    ip = state.get('ip') or (active_leases[0].get('ip') if active_leases else '')
    reachable = _buddy_reachable(ip)
    connected = recent or bool(active_leases) or reachable
    name = state.get('name') or (active_leases[0].get('name') if active_leases else '') or 'CYD Buddy'
    conn = _connection_state()
    settings = _settings_state() if include_settings else None
    payload = {
        'enabled': True,
        'connected': connected,
        'heartbeat_recent': recent,
        'reachable': reachable,
        'name': name,
        'ip': ip,
        'last_seen': state.get('last_seen'),
        'age_s': now - int(state.get('last_seen') or now) if state.get('last_seen') else None,
        'firmware': state.get('firmware') or '',
        'face': state.get('face') or '',
        'mood': state.get('mood') or '',
        'battery': state.get('battery'),
        'message': state.get('message') or '',
        'stats': state.get('stats') or {},
        'interactions': state.get('interactions') or {},
        'learning': state.get('learning') or {},
        'memory': state.get('memory') or {},
        'phrases': state.get('phrases') or {},
        'lifecycle': state.get('lifecycle') or {},
        'ai_state': state.get('ai_state') or {},
        'hotspot': conn,
        'leases': leases,
        'telemetry_url': f'http://{HOTSPOT_IP}:8766{TELEMETRY_PATH}',
        'heartbeat_url': f'http://{HOTSPOT_IP}:8766{HEARTBEAT_PATH}',
        'dashboard_url': f'http://{HOTSPOT_IP}:8766/',
        'dock_label': 'DOCKED' if connected else ('HOTSPOT READY' if conn.get('active') else 'HOTSPOT OFF'),
    }
    if include_settings:
        payload['settings'] = settings
    return payload


def telemetry_from_status(status: Dict[str, Any]) -> Dict[str, Any]:
    sys = status.get('system') or {}
    wifi = status.get('wifi') or {}
    sensors = status.get('sensors') or {}
    mood = status.get('mood') or {}
    cyd = cyd_status()
    host = socket.gethostname()
    buddy_event = _buddy_event_from_status(status)
    return {
        'ok': True,
        'time': _now(),
        'host': host,
        'buddy': cyd,
        'settings': cyd.get('settings') or _settings_state(),
        'mood': str(mood.get('name') or 'curious').lower(),
        'face': str(mood.get('face') or '(@-@)'),
        'color': mood.get('color') or '#38ff9c',
        'thought': status.get('thought') or '',
        'message': buddy_event.get('text') or '',
        'buddy_event': buddy_event,
        'system': {
            'hostname': sys.get('hostname') or host,
            'cpu_temp_c': sys.get('cpu_temp_c'),
            'cpu_temp_f': sys.get('cpu_temp_f'),
            'load': sys.get('load'),
            'memory': sys.get('memory'),
            'disk_root': sys.get('disk_root'),
            'uptime_s': sys.get('uptime_s'),
        },
        'wifi': {
            'connected': wifi.get('connected'),
            'ssid': (wifi.get('current') or {}).get('ssid'),
            'signal': (wifi.get('current') or {}).get('signal'),
            'networks': len(wifi.get('networks') or []),
        },
        'gps': sensors.get('gps') or {},
        'weather': sensors.get('weather') or {},
        'meshtastic': status.get('meshtastic') or {},
        'vision': status.get('vision') or {},
        'alert': status.get('alert') or {},
        'events': (status.get('events') or [])[:8],
        'next_poll_ms': 2000,
    }
