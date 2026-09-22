from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

from .paths import DATA_DIR

STATE_PATH = DATA_DIR / 'cyd_buddy.json'
LEASE_PATHS = (
    Path('/var/lib/NetworkManager/dnsmasq-wlan1.leases'),
    Path('/var/lib/NetworkManager/dnsmasq-Wu-Tang LAN.leases'),
    Path('/var/lib/misc/dnsmasq.leases'),
)
SSID = 'Wu-Tang LAN'
HOTSPOT_IP = '10.42.7.1'
TELEMETRY_PATH = '/api/cyd/telemetry'
HEARTBEAT_PATH = '/api/cyd/heartbeat'


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
    return {'ok': True, 'buddy': buddy}


def cyd_status() -> Dict[str, Any]:
    state = _read_json(STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}
    leases = _leases()
    now = _now()
    recent = bool(state.get('last_seen') and now - int(state.get('last_seen') or 0) <= 45)
    active_leases = [l for l in leases if l.get('active')]
    connected = recent or bool(active_leases)
    ip = state.get('ip') or (active_leases[0].get('ip') if active_leases else '')
    name = state.get('name') or (active_leases[0].get('name') if active_leases else '') or 'CYD Buddy'
    conn = _connection_state()
    return {
        'enabled': True,
        'connected': connected,
        'heartbeat_recent': recent,
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


def telemetry_from_status(status: Dict[str, Any]) -> Dict[str, Any]:
    sys = status.get('system') or {}
    wifi = status.get('wifi') or {}
    sensors = status.get('sensors') or {}
    mood = status.get('mood') or {}
    cyd = cyd_status()
    host = socket.gethostname()
    return {
        'ok': True,
        'time': _now(),
        'host': host,
        'buddy': cyd,
        'mood': str(mood.get('name') or 'curious').lower(),
        'face': str(mood.get('face') or '(@-@)'),
        'color': mood.get('color') or '#38ff9c',
        'thought': status.get('thought') or '',
        'message': status.get('thought') or '',
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
