from __future__ import annotations

import ipaddress
import json
import math
import os
import re
import secrets
import shutil
import socket
import string
import subprocess
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

from .config import load_config, save_config

DATA_DIR = Path('/home/pi/spac3-gh0st/data')
SEEN_FILE = DATA_DIR / 'seen.json'
KNOWN_DEVICES_FILE = DATA_DIR / 'known_devices.json'
STATUS_HISTORY_FILE = DATA_DIR / 'status_history.json'
WIFI_PSK_ACTIONS_FILE = DATA_DIR / 'wifi_psk_actions.json'
GPS_TRAIL_FILE = DATA_DIR / 'gps_trail.json'
HANDSHAKE_DIR = DATA_DIR / 'handshakes'
CAPTURE_STATE_FILE = DATA_DIR / 'handshake_capture.json'
CROWPI_STATUS = Path('/home/pi/Desktop/System-Controls/crowpi_status.py')
PWN_PLUGINS = Path('/home/pi/src/pwnagotchi/pwnagotchi/plugins')
_MEM_CACHE: Dict[str, Dict[str, Any]] = {}


def run(cmd: list[str], timeout: int = 8) -> str:
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=False).stdout
    except Exception as exc:
        return f'ERROR: {exc}'


def cached(key: str, ttl: float, fn):
    now = time.time()
    ent = _MEM_CACHE.get(key)
    if ent and now - ent['ts'] < ttl:
        data = ent['data']
        if isinstance(data, dict):
            data = dict(data)
            data['cached'] = True
        return data
    data = fn()
    _MEM_CACHE[key] = {'ts': now, 'data': data}
    if isinstance(data, dict):
        data = dict(data)
        data['cached'] = False
    return data


def split_nmcli(line: str) -> list[str]:
    parts, buf, esc = [], '', False
    for ch in line.rstrip('\n'):
        if esc:
            buf += ch
            esc = False
        elif ch == '\\':
            esc = True
        elif ch == ':':
            parts.append(buf)
            buf = ''
        else:
            buf += ch
    parts.append(buf)
    return parts


def parse_nmcli_wifi(text: str) -> List[Dict[str, Any]]:
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.startswith('ERROR'):
            continue
        parts = split_nmcli(line)
        while len(parts) < 5:
            parts.append('')
        active, ssid, chan, signal, security = parts[:5]
        rows.append({'connected': active.lower() == 'yes', 'ssid': ssid or '<hidden>', 'channel': chan, 'signal': signal, 'security': security})
    return rows


def wifi_status(rescan: bool = False) -> Dict[str, Any]:
    def collect():
        mode = 'yes' if rescan else 'no'
        text = run(['nmcli', '-t', '-f', 'ACTIVE,SSID,CHAN,SIGNAL,SECURITY', 'dev', 'wifi', 'list', '--rescan', mode], timeout=12 if rescan else 4)
        networks = parse_nmcli_wifi(text)
        current = next((n for n in networks if n['connected']), None)
        return {'available': True, 'connected': bool(current), 'current': current, 'networks': networks[:40], 'rescan': rescan}
    return cached('wifi_rescan' if rescan else 'wifi_fast', 12 if rescan else 3, collect)


def parse_bluetooth_devices(text: str) -> List[Dict[str, str]]:
    devices = []
    for line in text.splitlines():
        m = re.match(r'Device\s+([0-9A-Fa-f:]{17})\s*(.*)$', line.strip())
        if m:
            devices.append({'mac': m.group(1).upper(), 'name': m.group(2).strip() or 'Unknown'})
    return devices


def bluetooth_status(scan: bool = False) -> Dict[str, Any]:
    def collect():
        powered = 'Powered: yes' in run(['bluetoothctl', 'show'], timeout=3)
        if scan:
            # Short active scan; non-blocking enough for a button, not for every refresh.
            run(['timeout', '5', 'bluetoothctl', 'scan', 'on'], timeout=7)
            run(['bluetoothctl', 'scan', 'off'], timeout=3)
        devices = parse_bluetooth_devices(run(['bluetoothctl', 'devices'], timeout=4))
        return {'available': True, 'powered': powered, 'devices': devices[:80], 'scan': scan}
    return cached('bt_scan' if scan else 'bt_fast', 10 if scan else 4, collect)


def mac_vendor_hint(mac: str) -> str:
    prefix = mac.upper().replace('-', ':')[:8]
    hints = {'2C:CF:67': 'Raspberry Pi', 'B8:27:EB': 'Raspberry Pi', 'DC:A6:32': 'Raspberry Pi', 'E4:5F:01': 'Raspberry Pi', 'D8:3A:DD': 'Raspberry Pi', 'F4:F5:D8': 'Google/Nest', '3C:5C:C4': 'Amazon', 'F0:18:98': 'Apple'}
    return hints.get(prefix, 'Unknown')


def lan_status() -> Dict[str, Any]:
    def collect():
        arp = run(['ip', 'neigh', 'show'], timeout=3)
        devices = []
        for line in arp.splitlines():
            parts = line.split()
            if not parts:
                continue
            ip = parts[0]
            mac = ''
            state = parts[-1] if parts else ''
            if 'lladdr' in parts:
                mac = parts[parts.index('lladdr') + 1].upper()
            name = ''
            try:
                name = socket.gethostbyaddr(ip)[0]
            except Exception:
                pass
            devices.append({'ip': ip, 'mac': mac, 'vendor': mac_vendor_hint(mac) if mac else '', 'hostname': name, 'state': state})
        return {'available': True, 'devices': devices[:100]}
    return cached('lan', 5, collect)


def _mem_status() -> Dict[str, Any]:
    values: Dict[str, int] = {}
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            key, raw = line.split(':', 1)
            values[key] = int(raw.strip().split()[0])
        total = values.get('MemTotal', 0)
        available = values.get('MemAvailable', 0)
        used = max(total - available, 0)
        pct = round((used / total) * 100, 1) if total else None
        swap_total = values.get('SwapTotal', 0)
        swap_free = values.get('SwapFree', 0)
        swap_used = max(swap_total - swap_free, 0)
        swap_pct = round((swap_used / swap_total) * 100, 1) if swap_total else 0
        total_mb = round(total / 1024)
        used_mb = round(used / 1024)
        available_mb = round(available / 1024)
        return {
            'total_mb': total_mb,
            'used_mb': used_mb,
            'available_mb': available_mb,
            'free_mb': round(values.get('MemFree', 0) / 1024),
            'buffers_mb': round(values.get('Buffers', 0) / 1024),
            'cached_mb': round((values.get('Cached', 0) + values.get('SReclaimable', 0) - values.get('Shmem', 0)) / 1024),
            'swap_total_mb': round(swap_total / 1024),
            'swap_used_mb': round(swap_used / 1024),
            'swap_free_mb': round(swap_free / 1024),
            'swap_percent': swap_pct,
            'percent': pct,
            'text': f"{used_mb}/{total_mb}MB {pct}%" if pct is not None else 'n/a',
            'detail_text': f"{used_mb} MB used out of {total_mb} MB; {available_mb} MB available" if pct is not None else 'n/a',
        }
    except Exception:
        return {'text': 'n/a'}


def _load_status() -> str:
    try:
        return ' '.join(f'{v:.2f}' for v in __import__('os').getloadavg())
    except Exception:
        return 'n/a'


def _cpu_times() -> Dict[str, int]:
    try:
        first = Path('/proc/stat').read_text().splitlines()[0].split()[1:]
        vals = [int(x) for x in first]
        keys = ['user', 'nice', 'system', 'idle', 'iowait', 'irq', 'softirq', 'steal', 'guest', 'guest_nice']
        return {k: vals[i] if i < len(vals) else 0 for i, k in enumerate(keys)}
    except Exception:
        return {}


def _cpu_model() -> str:
    try:
        for line in Path('/proc/cpuinfo').read_text(errors='ignore').splitlines():
            if line.lower().startswith(('model name', 'hardware', 'model')) and ':' in line:
                val = line.split(':', 1)[1].strip()
                if val:
                    return val
    except Exception:
        pass
    return ''


def _throttle_status() -> Dict[str, Any]:
    raw = run(['vcgencmd', 'get_throttled'], timeout=2).strip() if shutil.which('vcgencmd') else ''
    code = 0
    if raw.startswith('throttled='):
        try:
            code = int(raw.split('=', 1)[1], 16)
        except Exception:
            code = 0
    flags = []
    mapping = [(0, 'under-voltage now'), (1, 'frequency capped now'), (2, 'throttled now'), (3, 'soft temp limit now'), (16, 'under-voltage occurred'), (17, 'frequency capped occurred'), (18, 'throttled occurred'), (19, 'soft temp limit occurred')]
    for bit, label in mapping:
        if code & (1 << bit):
            flags.append(label)
    return {'raw': raw or 'n/a', 'code': code, 'flags': flags, 'ok': not flags}


def _cpu_live_status() -> Dict[str, Any]:
    now = time.time()
    cur = _cpu_times()
    prev = _MEM_CACHE.get('cpu_times_prev')
    _MEM_CACHE['cpu_times_prev'] = {'ts': now, 'data': cur}
    pct = None
    if cur and prev and isinstance(prev.get('data'), dict):
        old = prev['data']
        idle_now = cur.get('idle', 0) + cur.get('iowait', 0)
        idle_old = int(old.get('idle', 0)) + int(old.get('iowait', 0))
        total_now = sum(cur.values())
        total_old = sum(int(v) for v in old.values())
        total_delta = max(1, total_now - total_old)
        idle_delta = max(0, idle_now - idle_old)
        pct = round((1 - (idle_delta / total_delta)) * 100, 1)
    cores = []
    try:
        for line in Path('/proc/stat').read_text().splitlines():
            if re.match(r'^cpu\d+\s', line):
                name = line.split()[0]
                cores.append({'name': name, 'raw': [int(x) for x in line.split()[1:8]]})
    except Exception:
        pass
    freq_mhz = None
    try:
        freq_mhz = round(int(Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq').read_text().strip()) / 1000, 1)
    except Exception:
        pass
    governor = ''
    try:
        governor = Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor').read_text().strip()
    except Exception:
        pass
    return {'available': bool(cur), 'percent': pct, 'freq_mhz': freq_mhz, 'governor': governor, 'model': _cpu_model(), 'cores': len(cores) or os.cpu_count() or 0, 'load_percent_1m': round((os.getloadavg()[0] / max(1, os.cpu_count() or 1)) * 100, 1) if hasattr(os, 'getloadavg') else None, 'throttle': _throttle_status()}


def _disk_all_status() -> List[Dict[str, Any]]:
    rows = []
    text = run(['df', '-h', '-x', 'tmpfs', '-x', 'devtmpfs'], timeout=3)
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6:
            rows.append({'filesystem': parts[0], 'size': parts[1], 'used': parts[2], 'avail': parts[3], 'use_percent': parts[4], 'mount': parts[5]})
    return rows[:12]


def _top_processes(limit: int = 10) -> List[Dict[str, Any]]:
    rows = []
    text = run(['ps', '-eo', 'pid,comm,%cpu,%mem', '--sort=-%cpu'], timeout=3)
    for line in text.splitlines()[1:limit+1]:
        parts = line.split(None, 3)
        if len(parts) >= 4:
            rows.append({'pid': parts[0], 'command': parts[1], 'cpu': parts[2], 'memory': parts[3]})
    return rows


def _running_services(limit: int = 18) -> List[Dict[str, Any]]:
    rows = []
    text = run(['systemctl', 'list-units', '--type=service', '--state=running', '--no-legend', '--no-pager'], timeout=4)
    for line in text.splitlines()[:limit]:
        parts = line.split(None, 4)
        if parts:
            rows.append({'unit': parts[0], 'load': parts[1] if len(parts)>1 else '', 'active': parts[2] if len(parts)>2 else 'running', 'description': parts[4] if len(parts)>4 else ''})
    return rows


def _net_io_status() -> Dict[str, Any]:
    now = time.time()
    rows: Dict[str, Dict[str, int]] = {}
    try:
        for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
            if ':' not in line:
                continue
            iface, rest = line.split(':', 1)
            iface = iface.strip()
            if iface == 'lo':
                continue
            parts = rest.split()
            if len(parts) >= 16:
                rows[iface] = {'rx_bytes': int(parts[0]), 'tx_bytes': int(parts[8])}
    except Exception as exc:
        return {'available': False, 'error': str(exc), 'interfaces': {}}
    prev = _MEM_CACHE.get('net_io_prev')
    rates = {}
    if prev and isinstance(prev.get('data'), dict):
        elapsed = max(0.001, now - float(prev.get('ts', now)))
        for iface, vals in rows.items():
            old = prev['data'].get(iface, {})
            rates[iface] = {
                'rx_bps': max(0, round((vals['rx_bytes'] - int(old.get('rx_bytes', vals['rx_bytes']))) / elapsed, 1)),
                'tx_bps': max(0, round((vals['tx_bytes'] - int(old.get('tx_bytes', vals['tx_bytes']))) / elapsed, 1)),
            }
    _MEM_CACHE['net_io_prev'] = {'ts': now, 'data': rows}
    total_rx = sum(v.get('rx_bps', 0) for v in rates.values())
    total_tx = sum(v.get('tx_bps', 0) for v in rates.values())
    return {'available': True, 'interfaces': rows, 'rates': rates, 'rx_bps': round(total_rx, 1), 'tx_bps': round(total_tx, 1)}


def _device_memory_status(status: Dict[str, Any]) -> Dict[str, Any]:
    seen = _load_seen()
    totals = {key: len(seen.get(key, []) or []) for key in ('wifi', 'bluetooth', 'lan')}
    new_counts = {key: int(status.get(key, {}).get('new_count', 0) or 0) for key in ('wifi', 'bluetooth', 'lan')}
    return {'totals': totals, 'new_counts': new_counts, 'total_known': sum(totals.values()), 'total_new': sum(new_counts.values())}


def _recent_log_lines(limit: int = 8) -> List[str]:
    log = DATA_DIR.parent / 'logs' / 'server.log'
    try:
        if not log.exists():
            return []
        lines = log.read_text(errors='ignore').splitlines()[-limit:]
        return [line[-180:] for line in lines if line.strip()]
    except Exception as exc:
        return [f'log read error: {exc}']


def system_status() -> Dict[str, Any]:
    temp = None
    try:
        temp = int(Path('/sys/class/thermal/thermal_zone0/temp').read_text().strip()) / 1000.0
    except Exception:
        pass
    df_lines = run(['df', '-h', '/'], timeout=2).splitlines()
    disk_root = df_lines[-1] if df_lines else ''
    return {
        'hostname': socket.gethostname(),
        'uptime_s': int(float(Path('/proc/uptime').read_text().split()[0])),
        'cpu_temp_c': temp,
        'cpu_temp_f': round((temp * 9 / 5) + 32, 1) if isinstance(temp, (int, float)) else None,
        'load': _load_status(),
        'cpu_live': _cpu_live_status(),
        'memory': _mem_status(),
        'ips': run(['hostname', '-I'], timeout=2).strip().split(),
        'disk_root': disk_root,
        'disk_all': _disk_all_status(),
        'net_io': _net_io_status(),
        'top_processes': _top_processes(),
        'running_services': _running_services(),
        'fan': fan_status(),
    }


def service_status(names=('jellyfin', 'ssh', 'tailscaled', 'gpsd')) -> Dict[str, Any]:
    def collect():
        out = {}
        for name in names:
            active = run(['systemctl', 'is-active', name], timeout=2).strip()
            enabled = run(['systemctl', 'is-enabled', name], timeout=2).strip()
            out[name] = {'active': active == 'active', 'active_text': active, 'enabled': enabled == 'enabled', 'enabled_text': enabled}
        return out
    return cached('services', 8, collect)


def _tilt_level_raw() -> int:
    try:
        sensors = load_config().setdefault('sensors', {})
        return int(sensors.get('tilt_level_raw', 1))
    except Exception:
        return 1


def _normalize_tilt(raw: Any) -> tuple[str, int, int]:
    level_raw = _tilt_level_raw()
    try:
        raw_i = int(raw)
    except Exception:
        return 'UNKNOWN', 0, level_raw
    if raw_i == level_raw:
        return 'LEVEL', 0, level_raw
    return 'TILTED', 28, level_raw


def calibrate_tilt_level(raw: Any | None = None) -> Dict[str, Any]:
    if raw is None:
        try:
            import RPi.GPIO as GPIO  # type: ignore
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            raw = int(GPIO.input(22))
            GPIO.cleanup(22)
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}
    try:
        raw_i = int(raw)
    except Exception:
        return {'ok': False, 'error': f'invalid raw tilt value: {raw!r}'}
    cfg = load_config()
    cfg.setdefault('sensors', {})['tilt_level_raw'] = raw_i
    save_config(cfg)
    state_file = DATA_DIR / 'tilt_state.json'
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({'current': f'{raw_i}:LEVEL', 'ts': time.time(), 'raw': raw_i, 'orientation': 'LEVEL'}))
    return {'ok': True, 'raw': raw_i, 'orientation': 'LEVEL', 'message': f'CrowPi tilt calibrated: raw {raw_i} is LEVEL.'}


def _annotate_tilt_event(data: Dict[str, Any]) -> Dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state_file = DATA_DIR / 'tilt_state.json'
    gpio = data.get('gpio', {}) if isinstance(data, dict) else {}
    raw = gpio.get('tilt')
    # CrowPi tilt is a binary switch, not an accelerometer. Interpret it through
    # the user-calibrated physical level raw value, and keep raw visible in the UI.
    orientation, angle, level_raw = _normalize_tilt(raw)
    gpio['tiltLevelRaw'] = level_raw
    gpio['tiltRaw'] = raw
    gpio['tiltOrientation'] = orientation
    gpio['tiltAngle'] = angle
    gpio['tiltLabel'] = orientation if orientation != 'UNKNOWN' else gpio.get('tiltLabel', 'UNKNOWN')
    data['gpio'] = gpio
    current = f'{raw}:{orientation}' if raw is not None else orientation
    now = time.time()
    event = {'changed': False, 'fast': False, 'current': current, 'previous': None, 'age_s': None, 'raw': raw, 'orientation': orientation, 'angle': angle, 'level_raw': level_raw}
    try:
        previous = json.loads(state_file.read_text()) if state_file.exists() else {}
    except Exception:
        previous = {}
    if current is not None:
        event['previous'] = previous.get('current')
        event['age_s'] = now - previous.get('ts', now) if previous else None
        if previous and previous.get('current') != current:
            event['changed'] = True
            event['fast'] = (now - previous.get('ts', now)) <= 12
        state_file.write_text(json.dumps({'current': current, 'ts': now, 'raw': raw, 'orientation': orientation}))
    data['tilt_event'] = event
    return data



def tilt_status() -> Dict[str, Any]:
    """Fast GPIO-only tilt readout for live UI updates; avoids full GPS/I2C/weather collection."""
    data: Dict[str, Any] = {'gpio': {'available': False, 'tilt': None, 'tiltLabel': 'UNKNOWN', 'error': None}}
    try:
        import RPi.GPIO as GPIO  # type: ignore
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        raw = int(GPIO.input(22))
        GPIO.cleanup(22)
        orientation, _angle, level_raw = _normalize_tilt(raw)
        data['gpio'].update({'available': True, 'tilt': raw, 'tiltLevelRaw': level_raw, 'tiltLabel': orientation})
    except Exception as exc:
        data['gpio']['error'] = str(exc)
    annotated = _annotate_tilt_event(data)
    annotated['ts'] = time.time()
    annotated['live'] = True
    return annotated


def fan_status() -> Dict[str, Any]:
    out: Dict[str, Any] = {'available': False, 'cooling_state': None, 'cooling_max': None, 'rpm': None, 'pwm': None, 'pwm_enable': None, 'note': 'kernel controlled'}
    try:
        import glob
        for t in glob.glob('/sys/class/thermal/cooling_device*/type'):
            base = Path(t).parent
            if base.joinpath('type').read_text().strip() == 'pwm-fan':
                out['available'] = True
                out['cooling_state'] = int(base.joinpath('cur_state').read_text().strip())
                out['cooling_max'] = int(base.joinpath('max_state').read_text().strip())
        for h in glob.glob('/sys/class/hwmon/hwmon*'):
            base = Path(h)
            name = base.joinpath('name').read_text().strip() if base.joinpath('name').exists() else ''
            if name == 'pwmfan':
                out['available'] = True
                if base.joinpath('fan1_input').exists(): out['rpm'] = int(base.joinpath('fan1_input').read_text().strip())
                if base.joinpath('pwm1').exists(): out['pwm'] = int(base.joinpath('pwm1').read_text().strip())
                if base.joinpath('pwm1_enable').exists(): out['pwm_enable'] = int(base.joinpath('pwm1_enable').read_text().strip())
    except Exception as exc:
        out['error'] = str(exc)
    return out


def sensor_status(force: bool = False) -> Dict[str, Any]:
    cache = DATA_DIR / 'crowpi_status_cache.json'
    if not force and cache.exists() and (time.time() - cache.stat().st_mtime) <= 30:
        try:
            data = json.loads(cache.read_text())
            data = _annotate_tilt_event(data)
            data['cached'] = True
            data['cache_age_s'] = round(time.time() - cache.stat().st_mtime, 1)
            return data
        except Exception:
            pass
    def collect():
        if not CROWPI_STATUS.exists():
            return {'available': False, 'error': f'{CROWPI_STATUS} not found'}
        text = run(['python3', str(CROWPI_STATUS)], timeout=10)
        try:
            data = _annotate_tilt_event(json.loads(text))
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data))
            return data
        except Exception as exc:
            if cache.exists():
                try:
                    data = json.loads(cache.read_text())
                    data = _annotate_tilt_event(data)
                    data['stale'] = True
                    data['cache_error'] = str(exc)
                    return data
                except Exception:
                    pass
            return {'available': False, 'error': str(exc), 'raw': text[:500]}
    return cached('sensors_force' if force else 'sensors', 4 if force else 60, collect)


def pwnagotchi_plugins() -> List[Dict[str, Any]]:
    def collect():
        plugins = []
        if not PWN_PLUGINS.exists():
            return plugins
        for path in sorted(PWN_PLUGINS.rglob('*.py')):
            txt = path.read_text(errors='ignore')[:20000]
            dangerous = any(k in txt.lower() for k in ['deauth', 'handshake', 'bettercap', 'wpa-sec', 'onlinehashcrack'])
            callbacks = sorted(set(re.findall(r'def\s+(on_[a-zA-Z0-9_]+)', txt)))
            plugins.append({'name': path.stem, 'path': str(path), 'callbacks': callbacks, 'auto_load': False, 'compatibility': 'shim-needed', 'safe_default': not dangerous})
        return plugins
    return cached('pwn_plugins', 300, collect)


def parse_nmcli_connection_names(text: str) -> List[Dict[str, str]]:
    rows = []
    for line in text.splitlines():
        parts = split_nmcli(line)
        if len(parts) >= 2 and parts[1] == '802-11-wireless':
            rows.append({'name': parts[0], 'type': parts[1]})
    return rows


def known_wifi_passwords(reveal: bool = False) -> Dict[str, Any]:
    rows = []
    for conn in parse_nmcli_connection_names(run(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'], timeout=4)):
        name = conn['name']
        detail = run(['nmcli', '--show-secrets', 'connection', 'show', name], timeout=4)
        ssid = name
        psk = ''
        for line in detail.splitlines():
            if line.strip().startswith('802-11-wireless.ssid:'):
                ssid = line.split(':', 1)[1].strip() or name
            if line.strip().startswith('802-11-wireless-security.psk:'):
                psk = line.split(':', 1)[1].strip()
        rows.append({'name': name, 'ssid': ssid, 'password': psk if reveal else ('••••••••' if psk else ''), 'has_password': bool(psk), 'revealed': reveal})
    return {'available': True, 'revealed': reveal, 'networks': rows}


def _load_seen() -> Dict[str, list]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text())
        except Exception:
            pass
    return {'wifi': [], 'bluetooth': [], 'lan': []}


def _save_seen(seen: Dict[str, list]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=2, sort_keys=True))


def mark_new(status: Dict[str, Any]) -> Dict[str, Any]:
    seen = _load_seen()
    wifi_ids = [n.get('ssid', '') for n in status.get('wifi', {}).get('networks', []) if n.get('ssid')]
    bt_ids = [d.get('mac', '') for d in status.get('bluetooth', {}).get('devices', []) if d.get('mac')]
    lan_ids = [d.get('ip', '') for d in status.get('lan', {}).get('devices', []) if d.get('ip')]
    for key, ids in (('wifi', wifi_ids), ('bluetooth', bt_ids), ('lan', lan_ids)):
        old = set(seen.get(key, []))
        new = [x for x in ids if x and x not in old]
        status.setdefault(key, {})['new_count'] = len(new)
        status.setdefault(key, {})['new'] = new[:10]
        seen[key] = sorted(old.union(ids))[-500:]
    _save_seen(seen)
    return status


def _primary_lan_network() -> tuple[str, str]:
    route = run(['ip', '-4', 'route', 'show', 'default'], timeout=2).splitlines()
    iface = ''
    src = ''
    if route:
        parts = route[0].split()
        if 'dev' in parts:
            iface = parts[parts.index('dev') + 1]
        if 'src' in parts:
            src = parts[parts.index('src') + 1]
    if not src and iface:
        addr = run(['ip', '-4', '-o', 'addr', 'show', iface], timeout=2)
        m = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', addr)
        if m:
            src = m.group(1)
            prefix = int(m.group(2))
            net = ipaddress.ip_network(f'{src}/{prefix}', strict=False)
            return str(net), iface
    if src:
        return str(ipaddress.ip_network(f'{src}/24', strict=False)), iface or 'unknown'
    return '', iface or 'unknown'


def _tcp_probe(ip: str, port: int, timeout: float = 0.22) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def active_recon(max_hosts: int = 128) -> Dict[str, Any]:
    """Authorized active local LAN recon: ping sweep + small TCP port check.

    This intentionally stays on the primary RFC1918 LAN and does not do deauth,
    exploitation, credential guessing, or internet-wide scanning.
    """
    started = time.time()
    network_text, iface = _primary_lan_network()
    if not network_text:
        return {'ok': False, 'error': 'no primary IPv4 LAN found', 'scope': 'none', 'hosts': [], 'ports': []}
    network = ipaddress.ip_network(network_text, strict=False)
    if not network.is_private or network.prefixlen < 24:
        return {'ok': False, 'error': f'refusing broad/non-private scope {network}', 'scope': str(network), 'hosts': [], 'ports': []}
    hosts = [str(ip) for ip in network.hosts()][:max_hosts]
    common_ports = [22, 53, 80, 443, 445, 3000, 3001, 8080, 8765]

    def ping_host(ip: str) -> tuple[str, bool]:
        ping = run(['timeout', '0.7', 'ping', '-c', '1', '-W', '1', ip], timeout=1)
        live = ' 0% packet loss' in ping or ' 0.0% packet loss' in ping or '1 received' in ping
        return ip, live

    alive_ips = set()
    with ThreadPoolExecutor(max_workers=96) as pool:
        futs = [pool.submit(ping_host, ip) for ip in hosts]
        for fut in as_completed(futs):
            ip, live = fut.result()
            if live:
                alive_ips.add(ip)
    known = {d.get('ip'): d for d in lan_status().get('devices', []) if d.get('ip')}
    alive_ips.update(ip for ip in known if ipaddress.ip_address(ip) in network)

    def scan_ports(ip: str) -> Dict[str, Any]:
        open_ports = [port for port in common_ports if _tcp_probe(ip, port, timeout=0.08)]
        return {'ip': ip, 'alive': True, 'open_ports': open_ports}

    results = []
    with ThreadPoolExecutor(max_workers=64) as pool:
        futs = [pool.submit(scan_ports, ip) for ip in sorted(alive_ips, key=lambda x: tuple(int(p) for p in x.split('.')))[:48]]
        for fut in as_completed(futs):
            results.append(fut.result())
    for row in results:
        info = known.get(row['ip'], {})
        row['mac'] = info.get('mac', '')
        row['hostname'] = info.get('hostname', '')
        row['vendor'] = info.get('vendor', '')
    results.sort(key=lambda r: tuple(int(x) for x in r['ip'].split('.')))
    return {
        'ok': True,
        'scope': str(network),
        'iface': iface,
        'duration_s': round(time.time() - started, 2),
        'ports': common_ports,
        'host_count': len(results),
        'hosts': results[:80],
        'note': 'active local LAN ping/TCP sweep only; no deauth, exploit, credential, or internet scan',
    }


def _wifi_passphrase_score(psk: str) -> Dict[str, Any]:
    length = len(psk or '')
    classes = sum(bool(re.search(pattern, psk or '')) for pattern in (r'[a-z]', r'[A-Z]', r'[0-9]', r'[^A-Za-z0-9]'))
    score = 0
    score += 20 if length >= 12 else 8 if length >= 8 else 0
    score += 20 if length >= 16 else 0
    score += 20 if length >= 20 else 0
    score += min(classes * 10, 40)
    score = min(score, 100)
    label = 'strong' if score >= 80 else 'okay' if score >= 55 else 'weak'
    return {'length': length, 'classes': classes, 'score': score, 'label': label}


def _saved_wifi_audit() -> List[Dict[str, Any]]:
    rows = []
    for conn in parse_nmcli_connection_names(run(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'], timeout=4)):
        name = conn['name']
        detail = run(['nmcli', '--show-secrets', 'connection', 'show', name], timeout=4)
        ssid = name
        psk = ''
        security = ''
        for line in detail.splitlines():
            stripped = line.strip()
            if stripped.startswith('802-11-wireless.ssid:'):
                ssid = stripped.split(':', 1)[1].strip() or name
            elif stripped.startswith('802-11-wireless-security.key-mgmt:'):
                security = stripped.split(':', 1)[1].strip()
            elif stripped.startswith('802-11-wireless-security.psk:'):
                value = stripped.split(':', 1)[1].strip()
                psk = value if value and value != '--' else ''
        strength = _wifi_passphrase_score(psk) if psk else {'length': 0, 'classes': 0, 'score': 0, 'label': 'missing'}
        rows.append({'name': name, 'ssid': ssid, 'security': security or 'unknown', 'has_password': bool(psk), 'password_strength': strength})
    return rows[:30]


def _cmd_path(name: str) -> str:
    """Return a command path that works from systemd/minimal PATH contexts."""
    path = shutil.which(name)
    if path:
        return path
    for prefix in ('/usr/sbin', '/usr/bin', '/sbin', '/bin'):
        candidate = Path(prefix) / name
        if candidate.exists():
            return str(candidate)
    return name



def parse_iw_dev_interfaces(text: str) -> List[Dict[str, Any]]:
    """Parse `iw dev` into interface rows with name/type/channel.

    Kept pure/testable so Hack-Safe can show Pwnagotchi readiness without
    flipping adapters or disturbing the desktop Wi-Fi connection.
    """
    ifaces: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('Interface '):
            current = {'name': line.split(None, 1)[1], 'type': None, 'channel': None}
            ifaces.append(current)
        elif line.startswith('Unnamed/non-netdev interface'):
            current = {}
        elif current and line.startswith('type '):
            current['type'] = line.split(None, 1)[1]
        elif current and line.startswith('channel '):
            m = re.search(r'channel\s+(\d+)', line)
            current['channel'] = int(m.group(1)) if m else None
        elif current and line.startswith('ssid '):
            current['ssid'] = line.split(None, 1)[1]
    return ifaces


def parse_iw_phy_channels(text: str) -> List[int]:
    """Return enabled 802.11 channels from `iw phy` output."""
    channels: List[int] = []
    for raw in text.splitlines():
        line = raw.strip()
        if '(disabled)' in line:
            continue
        m = re.search(r'\[(\d+)\]', line)
        if m:
            ch = int(m.group(1))
            if 1 <= ch <= 196 and ch not in channels:
                channels.append(ch)
    return sorted(channels)


def pwn_channel_plan(networks: List[Dict[str, Any]], supported_channels: List[int] | None = None) -> List[Dict[str, Any]]:
    """Pwnagotchi-style channel priority: busier/stronger channels first.

    This is planning/visibility only. It does not set monitor mode, hop, deauth,
    associate, or capture traffic.
    """
    supported = list(supported_channels or [])
    stats: Dict[int, Dict[str, Any]] = {}
    for net in networks or []:
        raw = str(net.get('channel') or '').strip()
        if not raw.isdigit():
            continue
        ch = int(raw)
        if supported and ch not in supported:
            continue
        sig_raw = str(net.get('signal') or '0')
        signal = int(sig_raw) if sig_raw.isdigit() else 0
        entry = stats.setdefault(ch, {'channel': ch, 'aps': 0, 'max_signal': 0, 'ssids': []})
        entry['aps'] += 1
        entry['max_signal'] = max(entry['max_signal'], signal)
        ssid = net.get('ssid') or '<hidden>'
        if ssid not in entry['ssids'] and len(entry['ssids']) < 5:
            entry['ssids'].append(ssid)
    for ch in supported:
        stats.setdefault(ch, {'channel': ch, 'aps': 0, 'max_signal': 0, 'ssids': []})
    return sorted(stats.values(), key=lambda row: (-row['aps'], -row['max_signal'], row['channel']))[:24]


def build_owned_lab_capture_plan(interface: str, bssid: str = '', channel: int | None = None, owned_lab: bool = False, capture_dir: str = '/home/pi/spac3-gh0st/data/handshakes') -> Dict[str, Any]:
    """Return a passive WPA handshake capture command plan for an owned lab only."""
    if not owned_lab:
        return {'ok': False, 'error': 'Refusing capture plan without owned_lab=true. Use only against CAK3D-owned lab networks/adapters.'}
    if not interface:
        return {'ok': False, 'error': 'monitor interface is required'}
    if bssid and not re.fullmatch(r'(?i)[0-9a-f]{2}(:[0-9a-f]{2}){5}', bssid):
        return {'ok': False, 'error': 'invalid BSSID format'}
    argv = ['airodump-ng', '-w', f'{capture_dir}/capture', '--output-format', 'pcap']
    if bssid:
        argv += ['--bssid', bssid.upper()]
    if channel:
        argv += ['--channel', str(int(channel))]
    argv.append(interface)
    return {
        'ok': True,
        'mode': 'passive-owned-lab-plan',
        'argv': argv,
        'requires': ['compatible external USB Wi-Fi adapter', 'monitor-mode interface', 'written/explicit owned-lab authorization'],
        'blocked': ['deauth automation', 'third-party networks', 'credential cracking'],
    }


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _capture_files(prefix: str | None = None) -> List[Dict[str, Any]]:
    HANDSHAKE_DIR.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    suffixes = ('.cap', '.pcap', '.pcapng', '.csv', '.kismet.csv', '.netxml', '.log')
    prefix_name = Path(prefix).name if prefix else ''
    for path in sorted(HANDSHAKE_DIR.glob('*'), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
        if not path.is_file():
            continue
        if prefix_name and not path.name.startswith(prefix_name):
            continue
        if not any(path.name.endswith(s) for s in suffixes):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append({
            'name': path.name,
            'path': str(path),
            'size': stat.st_size,
            'modified': int(stat.st_mtime),
            'kind': 'pcap' if path.suffix in ('.cap', '.pcap', '.pcapng') else ('log' if path.suffix == '.log' else 'metadata'),
        })
    return rows[:80]


def handshake_capture_status() -> Dict[str, Any]:
    """Return passive capture state plus captured artifacts."""
    state: Dict[str, Any] = {}
    if CAPTURE_STATE_FILE.exists():
        try:
            state = json.loads(CAPTURE_STATE_FILE.read_text())
        except Exception as exc:
            state = {'ok': False, 'error': f'capture state unreadable: {exc}'}
    pid = int(state.get('pid') or 0) if isinstance(state, dict) else 0
    files = _capture_files(state.get('prefix') if isinstance(state, dict) else None)
    return {
        'ok': True,
        'mode': 'passive-owned-lab-capture-status',
        'running': _pid_alive(pid),
        'state': state,
        'files': files,
        'pcaps': [f for f in files if f.get('kind') == 'pcap'],
        'handshake_detection': 'pcap artifacts are collected; validate owned-home/lab captures with aircrack-ng or Wireshark',
    }


def stop_owned_lab_capture() -> Dict[str, Any]:
    """Stop the recorded passive owned-lab capture process, if one exists."""
    status = handshake_capture_status()
    state = status.get('state') or {}
    pid = int(state.get('pid') or 0)
    if not pid:
        return {'ok': False, 'error': 'no recorded capture pid', 'status': status}
    if not status.get('running'):
        return {'ok': True, 'stopped': False, 'message': 'capture process is already stopped', 'status': status}
    try:
        os.kill(pid, 15)
    except Exception as exc:
        return {'ok': False, 'error': f'failed to stop capture pid {pid}: {exc}', 'status': status}
    time.sleep(0.2)
    return {'ok': True, 'stopped': True, 'pid': pid, 'status': handshake_capture_status()}


def _monitor_interfaces(adapter: Dict[str, Any]) -> List[str]:
    return [i.get('name') for i in adapter.get('interfaces', []) if i.get('name') and i.get('type') == 'monitor']


def _preferred_external_wifi(adapter: Dict[str, Any]) -> Dict[str, Any] | None:
    """Pick a USB Wi-Fi adapter for RF work without touching wlan0."""
    interfaces = adapter.get('interfaces', []) or []
    external = set(adapter.get('external_adapters') or [])
    for iface in interfaces:
        name = str(iface.get('name') or '')
        if not name or name == 'wlan0':
            continue
        if name in external and iface.get('type') in ('managed', 'monitor', None):
            return iface
    for iface in interfaces:
        name = str(iface.get('name') or '')
        if name and name != 'wlan0':
            return iface
    return None


def monitor_mode_status(adapter: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Readiness for the external USB dongle monitor-mode workflow."""
    adapter = adapter or _iw_capabilities()
    monitors = _monitor_interfaces(adapter)
    preferred = _preferred_external_wifi(adapter) or {}
    base = str(preferred.get('name') or '')
    tools = adapter.get('tools') or {}
    can_enable = bool(base and base != 'wlan0' and adapter.get('monitor_supported') and (tools.get('airmon-ng') or tools.get('iw')))
    return {
        'monitor_interfaces': monitors,
        'active': bool(monitors),
        'preferred_interface': base,
        'preferred_driver': preferred.get('driver') or '',
        'preferred_type': preferred.get('type') or '',
        'monitor_interface_hint': monitors[0] if monitors else (base + 'mon' if base else 'wlan1mon'),
        'can_enable': can_enable,
        'can_disable': bool(monitors),
        'wlan0_protected': True,
        'ready_label': ('monitor interface live' if monitors else ('USB dongle ready; prep monitor mode when needed' if can_enable else 'no safe external monitor adapter ready')),
        'note': 'wlan0 stays managed/connected; monitor prep targets the external USB dongle only.',
    }


def set_monitor_mode(action: str, interface: str = '') -> Dict[str, Any]:
    """Enable/disable monitor mode on the external USB adapter only.

    Separate from capture start. Never targets wlan0 and never deauths/injects/cracks.
    """
    action = str(action or '').strip().lower()
    adapter = _iw_capabilities()
    status = monitor_mode_status(adapter)
    if action in ('status', 'check', ''):
        return {'ok': True, 'action': 'status', 'adapter': adapter, 'monitor': status}
    base = str(interface or status.get('preferred_interface') or '').strip()
    if action in ('enable', 'start', 'prep'):
        if not base or base == 'wlan0':
            return {'ok': False, 'error': 'No safe external USB Wi-Fi interface selected; wlan0 is protected.', 'adapter': adapter, 'monitor': status}
        if status.get('active'):
            return {'ok': True, 'message': f"Monitor mode already active on {', '.join(status.get('monitor_interfaces') or [])}.", 'adapter': adapter, 'monitor': status}
        names = {i.get('name') for i in adapter.get('interfaces', []) or []}
        if base not in names:
            return {'ok': False, 'error': f'Interface {base} is not visible right now.', 'adapter': adapter, 'monitor': status}
        if not status.get('can_enable'):
            return {'ok': False, 'error': status.get('ready_label') or 'Monitor mode cannot be safely enabled right now.', 'adapter': adapter, 'monitor': status}
        cmd = [_cmd_path('airmon-ng'), 'start', base] if shutil.which('airmon-ng') else [_cmd_path('iw'), 'dev', base, 'set', 'type', 'monitor']
        try:
            cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
        except Exception as exc:
            return {'ok': False, 'error': f'monitor prep failed: {exc}', 'adapter': adapter, 'monitor': status}
        time.sleep(1.0)
        after = _iw_capabilities()
        after_status = monitor_mode_status(after)
        ok = bool(after_status.get('active'))
        return {
            'ok': ok, 'action': 'enable', 'interface': base, 'cmd': ' '.join(cmd),
            'stdout': cp.stdout.strip()[-1200:], 'stderr': cp.stderr.strip()[-1200:],
            'message': f"Monitor mode ready on {', '.join(after_status.get('monitor_interfaces') or [])}; wlan0 left alone." if ok else 'Monitor prep ran but no monitor interface appeared.',
            'adapter': after, 'monitor': after_status,
        }
    if action in ('disable', 'stop'):
        monitors = status.get('monitor_interfaces') or []
        target = base if base in monitors else (monitors[0] if monitors else '')
        if not target:
            return {'ok': True, 'message': 'No monitor interface is active.', 'adapter': adapter, 'monitor': status}
        cmd = [_cmd_path('airmon-ng'), 'stop', target] if shutil.which('airmon-ng') else [_cmd_path('ip'), 'link', 'set', target, 'down']
        try:
            cp = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
        except Exception as exc:
            return {'ok': False, 'error': f'monitor stop failed: {exc}', 'adapter': adapter, 'monitor': status}
        time.sleep(1.0)
        after = _iw_capabilities()
        return {'ok': True, 'action': 'disable', 'interface': target, 'cmd': ' '.join(cmd), 'stdout': cp.stdout.strip()[-1200:], 'stderr': cp.stderr.strip()[-1200:], 'message': f'Monitor interface {target} stop requested; wlan0 untouched.', 'adapter': after, 'monitor': monitor_mode_status(after)}
    return {'ok': False, 'error': 'unsupported monitor action', 'adapter': adapter, 'monitor': status}


def start_owned_lab_capture(body: Dict[str, Any], popen_factory=None) -> Dict[str, Any]:
    """Start passive owned-lab capture only when explicit gates and hardware exist."""
    popen_factory = popen_factory or subprocess.Popen
    owned_lab = bool(body.get('owned_lab'))
    bssid = str(body.get('bssid') or '').strip().upper()
    channel_raw = body.get('channel')
    channel = int(channel_raw) if str(channel_raw or '').strip().isdigit() else None
    adapter = _iw_capabilities()
    monitor_ifaces = _monitor_interfaces(adapter)
    interface = str(body.get('interface') or (monitor_ifaces[0] if monitor_ifaces else '')).strip()
    current = handshake_capture_status()
    if current.get('running'):
        return {'ok': False, 'error': 'a passive capture is already running; stop it before starting another', 'status': current}
    plan = build_owned_lab_capture_plan(interface, bssid=bssid, channel=channel, owned_lab=owned_lab, capture_dir=str(HANDSHAKE_DIR))
    if not plan.get('ok'):
        return plan
    if interface not in monitor_ifaces:
        return {'ok': False, 'error': 'No monitor-mode interface is available yet. Plug in the USB Wi-Fi adapter, enable monitor mode, then retry.', 'adapter': adapter, 'plan': plan}
    if not adapter.get('tools', {}).get('airodump-ng'):
        return {'ok': False, 'error': 'airodump-ng is not installed/found; install aircrack-ng tooling before capture.', 'adapter': adapter, 'plan': plan}
    HANDSHAKE_DIR.mkdir(parents=True, exist_ok=True)
    started = int(time.time())
    prefix = HANDSHAKE_DIR / f'owned-lab-{started}'
    argv = ['airodump-ng', '-w', str(prefix), '--output-format', 'pcap']
    if bssid:
        argv += ['--bssid', bssid]
    if channel:
        argv += ['--channel', str(channel)]
    argv.append(interface)
    log_path = HANDSHAKE_DIR / f'owned-lab-{started}.log'
    with log_path.open('ab') as log:
        proc = popen_factory(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    state = {'ok': True, 'mode': 'passive-owned-lab-capture', 'pid': int(getattr(proc, 'pid', 0) or 0), 'argv': argv, 'started': started, 'prefix': str(prefix), 'log': str(log_path), 'interface': interface, 'bssid': bssid, 'channel': channel, 'blocked': ['deauth automation', 'third-party networks', 'credential cracking']}
    CAPTURE_STATE_FILE.write_text(json.dumps(state, indent=2))
    return state

def _iw_capabilities() -> Dict[str, Any]:
    iw = _cmd_path('iw')
    dev = run([iw, 'dev'], timeout=3)
    phy = run([iw, 'phy'], timeout=8)
    ifaces = parse_iw_dev_interfaces(dev)

    modes: List[str] = []
    in_modes = False
    for raw in phy.splitlines():
        line = raw.strip()
        if line == 'Supported interface modes:':
            in_modes = True
            continue
        if in_modes:
            if line.startswith('* '):
                modes.append(line[2:].strip())
            elif line and not line.startswith('*'):
                in_modes = False
    channels = parse_iw_phy_channels(phy)

    drivers: Dict[str, str] = {}
    external = []
    for iface in ifaces:
        name = iface.get('name')
        if not name:
            continue
        driver_path = Path('/sys/class/net') / name / 'device' / 'driver'
        try:
            driver = driver_path.resolve().name
        except Exception:
            driver = ''
        if driver:
            drivers[name] = driver
            iface['driver'] = driver
        try:
            dev_path = str((Path('/sys/class/net') / name).resolve())
            if '/usb' in dev_path.lower():
                external.append(name)
        except Exception:
            pass

    tools = {
        name: bool(shutil.which(name) or Path(f'/usr/bin/{name}').exists() or Path(f'/usr/sbin/{name}').exists())
        for name in ['airmon-ng', 'aircrack-ng', 'airodump-ng', 'aireplay-ng', 'bettercap', 'nmap', 'hcxdumptool', 'hcxpcapngtool']
    }
    # rtl88XXau/8812au dongles may not expose every mode cleanly in iw phy on
    # Raspberry Pi kernels, but airmon-ng can still prep them. Require a real
    # monitor interface before capture; this flag is only UI/readiness.
    monitor_supported = 'monitor' in modes or any(str(d).lower() in ('rtl88xxau', '88xxau', 'rtl8812au', '8812au') for d in drivers.values())
    note = (
        'monitor mode supported by detected phy; use only on CAK3D-owned lab networks'
        if monitor_supported else
        'detected Wi-Fi phy does not advertise monitor mode; add a USB adapter with monitor+injection support for Pwnagotchi-style RF capture'
    )
    result = {
        'available': bool(dev.strip() and not dev.startswith('ERROR')),
        'interfaces': ifaces,
        'modes': modes,
        'monitor_supported': monitor_supported,
        'drivers': drivers,
        'external_adapters': external,
        'tools': tools,
        'supported_channels': channels,
        'raw_note': note,
    }
    result['monitor_setup'] = monitor_mode_status(result)
    return result


def _wifi_security_flags(networks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flags = []
    channel_counts: Dict[str, int] = {}
    for n in networks:
        ch = str(n.get('channel') or '')
        if ch:
            channel_counts[ch] = channel_counts.get(ch, 0) + 1
    for n in networks[:40]:
        sec = str(n.get('security') or '').upper()
        issues = []
        if not sec or sec in ('--', 'NONE'):
            issues.append('open network')
        if 'WEP' in sec:
            issues.append('WEP legacy/unsafe')
        if 'WPA1' in sec or sec.strip() == 'WPA':
            issues.append('WPA1 legacy')
        if 'WPS' in sec:
            issues.append('WPS visible')
        sig = int(n.get('signal') or 0) if str(n.get('signal') or '').isdigit() else 0
        if n.get('connected') and sig < 35:
            issues.append('weak connected signal')
        ch = str(n.get('channel') or '')
        if ch and channel_counts.get(ch, 0) >= 5:
            issues.append(f'crowded channel {ch}')
        if issues:
            flags.append({'ssid': n.get('ssid'), 'channel': ch, 'signal': sig, 'security': n.get('security'), 'issues': issues})
    return flags[:16]


def rf_audit_status(force: bool = False) -> Dict[str, Any]:
    """GhostESP/Kali-inspired but safe RF audit deck, cached to keep /api/status light."""
    def collect():
        wifi = wifi_status(False)
        bt = bluetooth_status(False)
        networks = wifi.get('networks', []) or []
        current = wifi.get('current') or {}
        bt_show = run(['bluetoothctl', 'show'], timeout=3)
        discoverable = 'Discoverable: yes' in bt_show
        pairable = 'Pairable: yes' in bt_show
        warnings = _wifi_security_flags(networks)
        adapter = _iw_capabilities()
        channel_plan = pwn_channel_plan(networks, adapter.get('supported_channels') or [])
        monitor_setup = adapter.get('monitor_setup') or monitor_mode_status(adapter)
        capture_plan = build_owned_lab_capture_plan(
            next((i.get('name') for i in adapter.get('interfaces', []) if i.get('type') == 'monitor'), ''),
            owned_lab=False,
        )
        capture_plan['monitor_setup'] = monitor_setup
        capture_status = handshake_capture_status()
        saved = _saved_wifi_audit()
        weak_saved = [row for row in saved if row.get('password_strength', {}).get('score', 0) < 55 and row.get('has_password')]
        bt_warnings = []
        if discoverable:
            bt_warnings.append('controller discoverable')
        if pairable:
            bt_warnings.append('controller pairable')
        return {
            'available': True,
            'mode': 'owned-network audit only',
            'kali_requested': 'safe audit mode: no cracking/deauth/exploit workflow',
            'wifi': {
                'current': current,
                'networks_seen': len(networks),
                'channels': sorted(set(str(n.get('channel')) for n in networks if n.get('channel'))),
                'security_warnings': warnings,
                'saved_networks': saved,
                'weak_saved_count': len(weak_saved),
                'adapter': adapter,
                'pwnagotchi': {
                    'epoch_ready': bool(networks),
                    'channel_plan': channel_plan,
                    'handshake_capture': capture_plan,
                    'monitor_setup': monitor_setup,
                    'capture_status': capture_status,
                    'captured_pcaps': capture_status.get('pcaps', []),
                    'pattern': 'Pwnagotchi observes AP/client/channel state, prioritizes channels, and records handshakes from bettercap/pcap events. Spac3-Gh0st now exposes owned-lab passive capture lifecycle and artifact tracking for monitor-capable adapters.',
                },
            },
            'bluetooth': {
                'powered': bt.get('powered'),
                'devices_seen': len(bt.get('devices', []) or []),
                'discoverable': discoverable,
                'pairable': pairable,
                'warnings': bt_warnings,
                'devices': (bt.get('devices', []) or [])[:12],
            },
            'allowed_actions': ['scan nearby APs', 'scan bluetooth inventory', 'audit saved PSK strength locally', 'active LAN recon on private subnet', 'report monitor/injection tool readiness'],
            'blocked_actions': ['third-party network access', 'password cracking against unknown networks', 'deauth outside an isolated owned lab', 'Bluetooth exploitation', 'credential theft'],
            'note': 'Spac3-Gh0st now reports real Kali-style tool and adapter readiness. Full Pwnagotchi-style monitor/injection needs a compatible external USB Wi-Fi adapter when the onboard chip lacks monitor mode.',
        }
    return cached('rf_audit_force' if force else 'rf_audit', 5 if force else 60, collect)


def _float_or_none(value) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(value)
    except Exception:
        return None


def _openweather_key() -> str:
    try:
        cfg = _read_json_file(DATA_DIR / 'config.json', {})
        weather_cfg = cfg.get('weather', {}) if isinstance(cfg, dict) else {}
        key = weather_cfg.get('openweathermap_api_key') or weather_cfg.get('openweather_api_key')
        if key:
            return str(key).strip()
    except Exception:
        pass
    return os.environ.get('OPENWEATHER_API_KEY', '').strip()


def weather_tile_url(layer: str, z: str, x: str, y: str) -> tuple[bytes, str]:
    allowed = {'precipitation_new', 'clouds_new', 'temp_new', 'pressure_new', 'wind_new'}
    if layer not in allowed:
        raise ValueError('unsupported OpenWeather tile layer')
    key = _openweather_key()
    if not key:
        raise RuntimeError('OpenWeather API key not configured')
    url = f'https://tile.openweathermap.org/map/{layer}/{int(z)}/{int(x)}/{int(y)}.png?appid={urllib.parse.quote(key)}'
    with urllib.request.urlopen(url, timeout=8) as resp:
        return resp.read(), resp.headers.get('Content-Type') or 'image/png'


def weather_status(gps: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Real weather plus short forecast/radar metadata, cached away from hot refresh work."""
    def collect():
        query = ''
        source = 'ip'
        lat = lon = None
        if gps and gps.get('fixed') and gps.get('lat') is not None and gps.get('lon') is not None:
            lat = _float_or_none(gps.get('lat')); lon = _float_or_none(gps.get('lon'))
            if lat is not None and lon is not None:
                query = f'{lat},{lon}'
                source = 'gps'
        weather = {
            'available': False, 'source': source, 'location': None, 'lat': lat, 'lon': lon,
            'summary': None, 'tempC': None, 'tempF': None, 'humidity': None, 'windMph': None,
            'forecast': [], 'sunrise': None, 'sunset': None, 'moonrise': None, 'moonset': None, 'radar': {'provider': 'OpenWeatherMap', 'configured': bool(_openweather_key()), 'layers': ['precipitation_new', 'clouds_new', 'wind_new'], 'tile_proxy': '/api/weather/tile/{layer}/{z}/{x}/{y}.png'},
            'provider': 'wttr.in + optional OpenWeatherMap tiles', 'error': None,
        }
        try:
            url = 'https://wttr.in/' + urllib.parse.quote(query) + '?format=j1'
            with urllib.request.urlopen(url, timeout=6) as resp:
                data = json.loads(resp.read().decode('utf-8', errors='replace'))
            current = (data.get('current_condition') or [{}])[0]
            area = (data.get('nearest_area') or [{}])[0]
            names = area.get('areaName') or []
            regions = area.get('region') or []
            countries = area.get('country') or []
            loc = [names[0].get('value') if names else None, regions[0].get('value') if regions else None, countries[0].get('value') if countries else None]
            if weather['lat'] is None:
                weather['lat'] = _float_or_none(area.get('latitude'))
            if weather['lon'] is None:
                weather['lon'] = _float_or_none(area.get('longitude'))
            desc = current.get('weatherDesc') or []
            temp_c = _float_or_none(current.get('temp_C'))
            humidity = _float_or_none(current.get('humidity'))
            forecast = []
            for i, day in enumerate((data.get('weather') or [])[:5]):
                astronomy = (day.get('astronomy') or [{}])[0]
                if i == 0:
                    weather['sunrise'] = astronomy.get('sunrise')
                    weather['sunset'] = astronomy.get('sunset')
                    weather['moonrise'] = astronomy.get('moonrise')
                    weather['moonset'] = astronomy.get('moonset')
                hourly = (day.get('hourly') or [{}])
                noon = hourly[min(len(hourly)-1, 4)] if hourly else {}
                ddesc = noon.get('weatherDesc') or []
                max_c = _float_or_none(day.get('maxtempC'))
                min_c = _float_or_none(day.get('mintempC'))
                forecast.append({
                    'date': day.get('date'),
                    'summary': ddesc[0].get('value') if ddesc else '',
                    'highF': round(max_c * 9 / 5 + 32, 1) if max_c is not None else None,
                    'lowF': round(min_c * 9 / 5 + 32, 1) if min_c is not None else None,
                    'chanceRain': _float_or_none(noon.get('chanceofrain')),
                    'chanceSnow': _float_or_none(noon.get('chanceofsnow')),
                })
            weather.update({
                'available': True, 'location': ', '.join(str(x) for x in loc if x),
                'summary': desc[0].get('value') if desc else None, 'tempC': temp_c,
                'tempF': round(temp_c * 9 / 5 + 32, 1) if temp_c is not None else None,
                'humidity': humidity, 'windMph': _float_or_none(current.get('windspeedMiles')),
                'forecast': forecast,
            })
        except Exception as exc:
            weather['error'] = str(exc)
        return weather
    return cached('weather', 900, collect)


def security_stack_status() -> Dict[str, Any]:
    """Native Security Lab-style blue-team board: hardening, IDS, honeypot, logs/dashboard."""
    def tool(name: str) -> bool:
        return bool(shutil.which(name))
    def svc_state(name: str) -> Dict[str, Any]:
        active = run(['systemctl', 'is-active', name], timeout=2).strip() or 'unknown'
        enabled = run(['systemctl', 'is-enabled', name], timeout=2).strip() or 'unknown'
        return {'name': name, 'active': active == 'active', 'enabled': enabled == 'enabled', 'active_text': active, 'enabled_text': enabled}
    def file_exists(path: str) -> bool:
        try:
            return Path(path).exists()
        except Exception:
            return False
    repo_paths = ['/home/pi/apps/raspberry-pi-security-lab', '/home/pi/raspberry-pi-security-lab']
    repo_present = [p for p in repo_paths if file_exists(p)]
    ufw = run(['sh', '-lc', 'ufw status 2>/dev/null | head -1'], timeout=2).strip()
    fail2ban = svc_state('fail2ban')
    suricata = svc_state('suricata')
    cowrie = svc_state('cowrie')
    grafana = svc_state('grafana-server')
    loki = svc_state('loki')
    promtail = svc_state('promtail')
    lanes = [
        {
            'id': 'hardening', 'label': 'Phase 1 // Hardening', 'icon': '🛡️',
            'state': 'detected' if (tool('ufw') or fail2ban['active']) else 'staged',
            'installed': tool('ufw') or tool('fail2ban-client') or fail2ban['active'],
            'score': sum([tool('ufw'), tool('fail2ban-client'), fail2ban['active'], 'Status: active' in ufw]),
            'signals': [f'UFW: {ufw or ("installed" if tool("ufw") else "missing")}', f'fail2ban: {fail2ban["active_text"]}/{fail2ban["enabled_text"]}', 'SSH/firewall hardening is review-first on this Tailscale Pi'],
            'safe_use': 'Surface firewall/fail2ban/SSH posture. Do not apply hardening scripts from a generic button.'
        },
        {
            'id': 'ids', 'label': 'Phase 2 // IDS', 'icon': '📡',
            'state': 'running' if suricata['active'] else ('installed' if tool('suricata') else 'staged'),
            'installed': tool('suricata') or suricata['active'],
            'score': sum([tool('suricata'), suricata['active'], file_exists('/var/log/suricata/eve.json'), file_exists('/var/log/suricata/fast.log')]),
            'signals': [f'Suricata: {suricata["active_text"]}/{suricata["enabled_text"]}', f'eve.json: {file_exists("/var/log/suricata/eve.json")}', f'fast.log: {file_exists("/var/log/suricata/fast.log")}'],
            'safe_use': 'Show IDS readiness and log presence. Interface/rule install needs explicit approval.'
        },
        {
            'id': 'honeypot', 'label': 'Phase 3 // Honeypot', 'icon': '🍯',
            'state': 'running' if cowrie['active'] else ('installed' if (tool('cowrie') or file_exists('/opt/cowrie')) else 'staged'),
            'installed': tool('cowrie') or file_exists('/opt/cowrie') or cowrie['active'],
            'score': sum([tool('cowrie'), file_exists('/opt/cowrie'), cowrie['active'], file_exists('/opt/cowrie/var/log/cowrie/cowrie.json')]),
            'signals': [f'Cowrie: {cowrie["active_text"]}/{cowrie["enabled_text"]}', f'/opt/cowrie: {file_exists("/opt/cowrie")}', f'cowrie.json: {file_exists("/opt/cowrie/var/log/cowrie/cowrie.json")}'],
            'safe_use': 'Defensive decoy only; bind/isolate deliberately and never reuse real credentials.'
        },
        {
            'id': 'dashboard', 'label': 'Phase 4 // Logs + Dashboard', 'icon': '📊',
            'state': 'running' if grafana['active'] else ('installed' if tool('grafana-cli') else 'staged'),
            'installed': tool('grafana-cli') or grafana['active'] or loki['active'] or promtail['active'],
            'score': sum([grafana['active'], loki['active'], promtail['active'], tool('grafana-cli')]),
            'signals': [f'Grafana: {grafana["active_text"]}/{grafana["enabled_text"]}', f'Loki: {loki["active_text"]}/{loki["enabled_text"]}', f'Promtail: {promtail["active_text"]}/{promtail["enabled_text"]}'],
            'safe_use': 'Use Grafana/Loki/Promtail ideas for live Spac3-Gh0st panels or link to Grafana if installed.'
        },
    ]
    stacks = [
        {'id': 'securitylab', 'label': 'Raspberry Pi Security Lab', 'installed': bool(repo_present), 'signals': [f'repo paths: {", ".join(repo_present) if repo_present else "not cloned"}', 'scripts: hardening, Suricata, Cowrie, dashboard'], 'safe_use': 'Source integration only until each script is reviewed and approved.'},
        {'id': 'security_onion', 'label': 'Security Onion ideas', 'installed': any(tool(t) for t in ('suricata', 'zeek', 'so-status')), 'signals': ['Suricata IDS alerts', 'Zeek connection logs', 'PCAP/event triage', f"tools suricata={tool('suricata')} zeek={tool('zeek')}"], 'safe_use': 'Mirror/ingest LAN telemetry; do not run heavy SO stack on this Pi unless offloaded.'},
        {'id': 'honeypi', 'label': 'HoneyPi/Cowrie ideas', 'installed': cowrie['active'] or tool('cowrie'), 'signals': ['fake SSH/HTTP probes', 'connection attempts', 'source IP log'], 'safe_use': 'Defensive honeypot only; isolated ports, no credential reuse.'},
    ]
    return {
        'available': True,
        'mode': 'Security Lab blue-team board // defensive-only',
        'source': 'https://github.com/ExploitGd/raspberry-pi-security-lab',
        'architecture': ['UFW/fail2ban hardening', 'Suricata IDS', 'Cowrie honeypot', 'Promtail/Loki/Grafana dashboard'],
        'repo_present': bool(repo_present),
        'repo_paths': repo_present,
        'lanes': lanes,
        'stacks': stacks,
        'recommendations': ['Clone/stage the repo first, then review each script before running.', 'Surface Suricata/Cowrie/Grafana status here even when the upstream dashboard is not installed.', 'Keep firewall/SSH hardening manual so Tailscale recovery stays safe.']
    }



def _read_json_file(path: Path, default):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default


def _write_json_file(path: Path, data) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _device_key(kind: str, item: Dict[str, Any]) -> str:
    if kind == 'wifi':
        return str(item.get('ssid') or item.get('name') or '').strip()
    if kind == 'bluetooth':
        return str(item.get('mac') or item.get('addr') or item.get('name') or '').upper().strip()
    if kind == 'lan':
        return str(item.get('mac') or item.get('ip') or item.get('hostname') or '').upper().strip()
    return str(item.get('id') or item.get('name') or '').strip()


def _display_name(kind: str, item: Dict[str, Any]) -> str:
    return str(item.get('label') or item.get('name') or item.get('ssid') or item.get('hostname') or item.get('ip') or item.get('mac') or 'unknown')


def _device_items(status: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for n in status.get('wifi', {}).get('networks', []) or []:
        key = _device_key('wifi', n)
        if key and key != '<hidden>':
            rows.append({'kind': 'wifi', 'id': key, 'name': _display_name('wifi', n), 'signal': n.get('signal'), 'security': n.get('security'), 'connected': n.get('connected')})
    for d in status.get('bluetooth', {}).get('devices', []) or []:
        key = _device_key('bluetooth', d)
        if key:
            rows.append({'kind': 'bluetooth', 'id': key, 'name': _display_name('bluetooth', d), 'mac': d.get('mac')})
    for d in status.get('lan', {}).get('devices', []) or []:
        key = _device_key('lan', d)
        if key:
            rows.append({'kind': 'lan', 'id': key, 'name': _display_name('lan', d), 'ip': d.get('ip'), 'mac': d.get('mac'), 'vendor': d.get('vendor'), 'hostname': d.get('hostname')})
    return rows


def _known_map() -> Dict[str, Any]:
    return _read_json_file(KNOWN_DEVICES_FILE, {'devices': {}})


def update_known_device(kind: str, device_id: str, label: str | None = None, trusted: bool | None = None, watched: bool | None = None, forget: bool = False) -> Dict[str, Any]:
    data = _known_map()
    devices = data.setdefault('devices', {})
    key = f'{kind}:{device_id}'
    if forget:
        devices.pop(key, None)
        _write_json_file(KNOWN_DEVICES_FILE, data)
        return {'ok': True, 'forgot': key, 'known_devices': known_devices_status()}
    rec = devices.setdefault(key, {'kind': kind, 'id': device_id, 'first_seen': int(time.time()), 'label': '', 'trusted': False, 'watched': False})
    rec['last_seen'] = int(time.time())
    if label is not None:
        rec['label'] = str(label).strip()[:80]
    if trusted is not None:
        rec['trusted'] = bool(trusted)
    if watched is not None:
        rec['watched'] = bool(watched)
    _write_json_file(KNOWN_DEVICES_FILE, data)
    return {'ok': True, 'device': rec, 'known_devices': known_devices_status()}


def _wifi_network_by_ssid(ssid: str, status: Dict[str, Any] | None = None) -> Dict[str, Any]:
    ssid = str(ssid or '').strip()
    wifi = status.get('wifi', {}) if isinstance(status, dict) else wifi_status(False)
    for n in wifi.get('networks', []) or []:
        if str(n.get('ssid') or '').strip() == ssid:
            return dict(n)
    return {'ssid': ssid}


def _strong_wifi_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*-_=+?'
    return ''.join(secrets.choice(alphabet) for _ in range(max(16, min(int(length or 20), 32))))


def wifi_psk_action(ssid: str, action: str) -> Dict[str, Any]:
    """Concrete actions for weak saved PSK warnings without leaking secrets."""
    ssid = str(ssid or '').strip()
    action = str(action or '').strip().lower()
    if not ssid or ssid == '<hidden>':
        return {'ok': False, 'error': 'Pick a named saved Wi-Fi profile first.'}
    saved = _saved_wifi_audit()
    row = next((r for r in saved if str(r.get('ssid') or '') == ssid or str(r.get('name') or '') == ssid), None)
    if not row:
        return {'ok': False, 'error': f'No saved NetworkManager profile found for {ssid}.'}
    if action == 'review':
        data = _read_json_file(WIFI_PSK_ACTIONS_FILE, {})
        data[ssid] = {'reviewed_at': int(time.time()), 'score': (row.get('password_strength') or {}).get('score'), 'note': 'User reviewed weak PSK warning; router password must be changed on router/admin UI.'}
        _write_json_file(WIFI_PSK_ACTIONS_FILE, data)
        return {'ok': True, 'action': action, 'ssid': ssid, 'message': f'{ssid} weak-PSK warning marked reviewed. Actual fix is changing the router/AP password, then updating this saved profile.'}
    if action == 'generate':
        pw = _strong_wifi_password(22)
        return {'ok': True, 'action': action, 'ssid': ssid, 'password': pw, 'message': f'Generated a strong replacement password for {ssid}. Change it in the router/AP admin UI first, then reconnect devices.'}
    if action == 'forget':
        name = str(row.get('name') or ssid)
        cp = subprocess.run(['nmcli', 'connection', 'delete', name], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        return {'ok': cp.returncode == 0, 'action': action, 'ssid': ssid, 'profile': name, 'stdout': cp.stdout.strip(), 'stderr': cp.stderr.strip(), 'message': f'Deleted saved Wi-Fi profile {name}. Reconnect after fixing the router/AP password.' if cp.returncode == 0 else f'Failed to delete profile {name}.'}
    return {'ok': False, 'error': 'Unsupported weak-PSK action. Use review, generate, or forget.'}


def wifi_target_action(ssid: str, action: str, label: str | None = None) -> Dict[str, Any]:
    """Safe Wi-Fi row actions for the dashboard: memory + local audit only."""
    ssid = str(ssid or '').strip()
    action = str(action or '').strip().lower()
    if not ssid or ssid == '<hidden>':
        return {'ok': False, 'error': 'Select a named Wi-Fi network first.'}
    if action not in ('remember', 'trust', 'watch', 'untrust', 'unwatch', 'name', 'audit', 'connect-plan'):
        return {'ok': False, 'error': 'Unsupported Wi-Fi action. Allowed: remember/trust/watch/name/audit/connect-plan.'}
    net = _wifi_network_by_ssid(ssid)
    key_result: Dict[str, Any] | None = None
    if action in ('remember', 'trust', 'watch', 'untrust', 'unwatch', 'name'):
        key_result = update_known_device(
            'wifi', ssid,
            label=label if action == 'name' else None,
            trusted=True if action == 'trust' else False if action == 'untrust' else None,
            watched=True if action == 'watch' else False if action == 'unwatch' else None,
        )
    saved = _saved_wifi_audit()
    saved_row = next((r for r in saved if str(r.get('ssid') or '') == ssid), None)
    warnings = [w for w in _wifi_security_flags([net]) if w.get('ssid') == ssid]
    signal = int(net.get('signal') or 0) if str(net.get('signal') or '').isdigit() else 0
    channel = str(net.get('channel') or '')
    security = str(net.get('security') or 'unknown')
    findings = []
    if signal:
        findings.append(f'signal {signal}%')
    if channel:
        findings.append(f'channel {channel}')
    findings.append(f'security {security}')
    if saved_row:
        ps = saved_row.get('password_strength') or {}
        findings.append(f'saved profile: yes / strength {ps.get("label", "n/a")} {ps.get("score", "n/a")}%')
    else:
        findings.append('saved profile: not found or secret unavailable')
    for w in warnings:
        findings.extend(w.get('issues') or [])
    if action == 'connect-plan':
        msg = f'{ssid}: connect planning only. Use OS Wi-Fi settings/nmcli for actual connection; Spac3-Gh0st will not auto-join networks or expose credentials.'
    elif action == 'audit':
        msg = f'{ssid}: safe local audit complete.'
    else:
        msg = f'{ssid}: known-network memory updated.'
    return {'ok': True, 'ssid': ssid, 'action': action, 'network': net, 'known_result': key_result, 'findings': findings, 'warnings': warnings, 'saved': bool(saved_row), 'message': msg}


def known_devices_status(status: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = _known_map()
    devices = data.setdefault('devices', {})
    now = int(time.time())
    online_keys = set()
    if status:
        for item in _device_items(status):
            key = f"{item['kind']}:{item['id']}"
            online_keys.add(key)
            rec = devices.setdefault(key, {'kind': item['kind'], 'id': item['id'], 'first_seen': now, 'label': '', 'trusted': False, 'watched': False})
            rec['last_seen'] = now
            rec['last_name'] = item.get('name')
            rec['last_meta'] = {k: v for k, v in item.items() if k not in ('kind', 'id')}
        _write_json_file(KNOWN_DEVICES_FILE, data)
    rows = []
    for key, rec in sorted(devices.items(), key=lambda kv: (not kv[1].get('watched'), not kv[1].get('last_seen', 0), kv[0])):
        r = dict(rec)
        r['key'] = key
        r['online'] = key in online_keys if status else False
        r['display'] = r.get('label') or r.get('last_name') or r.get('id')
        rows.append(r)
    return {'available': True, 'total': len(rows), 'online': sum(1 for r in rows if r.get('online')), 'trusted': sum(1 for r in rows if r.get('trusted')), 'watched': sum(1 for r in rows if r.get('watched')), 'devices': rows[:80]}


def household_signals_status(status: Dict[str, Any]) -> Dict[str, Any]:
    """Correlate home signals so unknown scan hits stand out from household devices.

    This is intentionally conservative: labels come from Spac3-Gh0st known-device
    memory, configured external nodes, obvious local/Tailnet fixtures, and later
    Home Assistant entity imports when credentials are added. It does not guess a
    BT MAC is a light unless there is a remembered label or source evidence.
    """
    known = status.get('known_devices') or known_devices_status(status)
    devices = known.get('devices') or []
    external_labels = {
        '192.168.18.42': 'Jeffeybot Raspberry Pi car',
        '100.65.33.36': 'theBAK3RY Raspberry Pi / dashboards',
        'thebak3ry': 'theBAK3RY Raspberry Pi / dashboards',
    }
    home_services = [
        {'id': 'homeassistant', 'label': 'Home Assistant @ theBAK3RY', 'url': 'http://100.65.33.36:8123', 'role': 'entity source'},
        {'id': 'heimdall', 'label': 'Heimdall @ theBAK3RY', 'url': 'http://100.65.33.36:8080', 'role': 'dashboard'},
        {'id': 'ruview', 'label': 'RuView local mirror', 'url': 'http://100.75.120.80:8765/ruview/index.html', 'role': 'CSI/RF sensing UI'},
    ]
    rows = []
    unknown = []
    for d in devices[:80]:
        key = d.get('key') or f"{d.get('kind')}:{d.get('id')}"
        display = d.get('display') or d.get('last_name') or d.get('id') or key
        label = d.get('label') or ''
        identity = label or external_labels.get(str(d.get('id') or '')) or external_labels.get(str((d.get('last_meta') or {}).get('ip') or '')) or display
        confidence = 'known-label' if label else ('fixture' if identity != display else ('trusted' if d.get('trusted') else 'unmapped'))
        mapped = bool(label or d.get('trusted') or confidence == 'fixture')
        row = {
            'key': key, 'kind': d.get('kind'), 'id': d.get('id'), 'display': display,
            'identity': identity, 'mapped': mapped, 'confidence': confidence,
            'online': bool(d.get('online')), 'trusted': bool(d.get('trusted')), 'watched': bool(d.get('watched')),
            'reason': 'labeled/trusted household device' if mapped else 'unmapped scan hit — should stick out until labeled/trusted/ignored',
        }
        rows.append(row)
        if row['online'] and not row['mapped']:
            unknown.append(row)
    counts = {
        'known_total': known.get('total', len(devices)), 'online': known.get('online', 0),
        'mapped': sum(1 for r in rows if r['mapped']), 'unmapped_online': len(unknown),
        'wifi': sum(1 for r in rows if r['kind'] == 'wifi'),
        'bluetooth': sum(1 for r in rows if r['kind'] == 'bluetooth'),
        'lan': sum(1 for r in rows if r['kind'] == 'lan'),
    }
    return {
        'available': True,
        'mode': 'household identity correlation',
        'summary': f"{counts['mapped']} mapped // {counts['unmapped_online']} unmapped online // {counts['known_total']} remembered",
        'counts': counts,
        'services': home_services,
        'home_assistant': {
            'available': True,
            'url': 'http://100.65.33.36:8123',
            'entity_import': 'not configured yet — add a Home Assistant token/API bridge to map entities like Upstairs Light ↔ device/MAC/RSSI evidence',
        },
        'signals_used': ['LAN/ARP/IP neighbors', 'Wi‑Fi SSID/BSSID inventory', 'Bluetooth advertisements', 'known-device labels/trust/watch flags', 'external Pi/camera URLs', 'future Home Assistant entities'],
        'blocked_actions': ['secret extraction', 'device takeover', 'unapproved pairing/control', 'guessing identities without evidence'],
        'unknown_online': unknown[:12],
        'mapped_devices': [r for r in rows if r['mapped']][:16],
        'recent_devices': rows[:24],
    }


def _alert_status(status: Dict[str, Any]) -> Dict[str, Any]:
    """Layered dashboard attention score.

    The top-line meter is meant to answer: "should I look right now?" It should
    stay green during normal advisories like a saved-password hygiene finding or
    GPS temporarily lacking a fix. Those details still surface, but in calmer
    advisory/hygiene layers instead of inflating the urgent score.
    """
    score = 0
    urgent: List[Dict[str, Any]] = []
    advisory: List[Dict[str, Any]] = []
    hygiene: List[Dict[str, Any]] = []

    def add_urgent(kind: str, points: int, text: str, **extra):
        nonlocal score
        score += points
        urgent.append({'kind': kind, 'points': points, 'text': text, **extra})

    def add_advisory(kind: str, text: str, points: int = 0, **extra):
        advisory.append({'kind': kind, 'points': points, 'text': text, **extra})

    def add_hygiene(kind: str, text: str, **extra):
        hygiene.append({'kind': kind, 'points': 0, 'text': text, **extra})

    new_count = sum(int(status.get(k, {}).get('new_count', 0) or 0) for k in ('wifi', 'bluetooth', 'lan'))
    if new_count:
        add_urgent('new_contacts', min(40, new_count * 12), f'{new_count} new contact(s)', count=new_count)

    vpn = status.get('vpn', {})
    if vpn and not vpn.get('active') and not (vpn.get('active_connections') or []):
        add_advisory('vpn_off', 'VPN off', points=0)

    sys = status.get('system', {})
    if isinstance(sys.get('cpu_temp_f'), (int, float)) and sys['cpu_temp_f'] >= 158:
        add_urgent('cpu_hot', 25, 'CPU hot', temp_f=sys['cpu_temp_f'])

    mem_pct = (sys.get('memory') or {}).get('percent')
    if isinstance(mem_pct, (int, float)) and mem_pct >= 85:
        add_urgent('ram_pressure', 15, 'RAM pressure', percent=mem_pct)

    services = {**(status.get('services') or {}), **(status.get('controls') or {})}
    down = [k for k, v in services.items() if isinstance(v, dict) and k in ('tailscaled', 'gpsd', 'ssh', 'vnc', 'syncthing') and not v.get('active')]
    if down:
        add_urgent('service_down', min(20, len(down) * 5), 'service down: ' + ', '.join(down[:3]), services=down[:8])

    gps = (status.get('sensors') or {}).get('gps', {})
    if gps and not gps.get('fixed'):
        add_advisory('gps_no_fix', 'GPS no fix', points=0, satellites_visible=gps.get('satellitesVisible') or 0)

    rf = status.get('rf_audit', {})
    weak = ((rf.get('wifi') or {}).get('weak_saved_count') or 0)
    if weak:
        add_hygiene(
            'weak_saved_psk',
            f'{weak} saved Wi-Fi password(s) look weak',
            count=weak,
            recommendation='Rotate owned/important networks to 16+ random characters; forget old saved networks.'
        )

    known = status.get('known_devices', {})
    watched_online = [d.get('display') for d in known.get('devices', []) if d.get('watched') and d.get('online')]
    if watched_online:
        add_advisory('watched_online', 'watched online: ' + ', '.join(watched_online[:3]), points=0, devices=watched_online[:8])

    # If several non-urgent operational advisories pile up, nudge the meter a
    # little without making hygiene alone look like an incident.
    operational_advisories = [a for a in advisory if a['kind'] in ('vpn_off', 'gps_no_fix')]
    if len(operational_advisories) >= 3:
        score += 10
        advisory.append({'kind': 'advisory_cluster', 'points': 10, 'text': 'several low-priority advisories active'})

    score = min(100, score)
    if score >= 75: level, color = 'RED', '#ff5f56'
    elif score >= 50: level, color = 'ORANGE', '#ff8c2e'
    elif score >= 25: level, color = 'YELLOW', '#ffbd2e'
    else: level, color = 'GREEN', '#27c93f'

    reasons = [item['text'] for item in urgent]
    summary = reasons[0] if reasons else 'normal watch'
    return {
        'level': level,
        'score': score,
        'color': color,
        'reasons': reasons or ['normal watch'],
        'summary': summary,
        'layers': {
            'urgent': urgent,
            'advisory': advisory,
            'hygiene': hygiene,
        },
    }


def _update_gps_trail(gps: Dict[str, Any]) -> Dict[str, Any]:
    trail = _read_json_file(GPS_TRAIL_FILE, [])
    if gps.get('fixed') and gps.get('lat') is not None and gps.get('lon') is not None:
        point = {'ts': int(time.time()), 'lat': gps.get('lat'), 'lon': gps.get('lon'), 'mode': gps.get('modeLabel'), 'used': gps.get('satellitesUsed')}
        if not trail or trail[-1].get('lat') != point['lat'] or trail[-1].get('lon') != point['lon']:
            trail.append(point)
            trail = trail[-80:]
            _write_json_file(GPS_TRAIL_FILE, trail)
    return {'points': trail[-30:], 'count': len(trail), 'last_fix': trail[-1] if trail else None}


def _update_status_history(status: Dict[str, Any]) -> Dict[str, Any]:
    hist = _read_json_file(STATUS_HISTORY_FILE, [])
    sys = status.get('system', {})
    gps = (status.get('sensors') or {}).get('gps', {})
    rec = {'ts': int(time.time()), 'cpu_f': sys.get('cpu_temp_f'), 'load': str(sys.get('load') or '').split()[0] if sys.get('load') else None, 'ram': (sys.get('memory') or {}).get('percent'), 'alert': (status.get('alert') or {}).get('level'), 'gps_fixed': gps.get('fixed')}
    if not hist or int(hist[-1].get('ts', 0)) <= rec['ts'] - 20:
        hist.append(rec); hist = hist[-180:]; _write_json_file(STATUS_HISTORY_FILE, hist)
    return {'points': hist[-60:], 'count': len(hist)}


def _rf_recommendations(status: Dict[str, Any]) -> List[str]:
    rf = status.get('rf_audit', {})
    wifi = rf.get('wifi', {}) if isinstance(rf, dict) else {}
    recs = []
    if wifi.get('weak_saved_count'):
        recs.append('Rotate weak saved Wi-Fi passphrases; prefer 16+ random chars.')
    if wifi.get('security_warnings'):
        recs.append('Review nearby/open/legacy/crowded AP warnings before blaming ghosts.')
    bt = rf.get('bluetooth', {}) if isinstance(rf, dict) else {}
    if bt.get('discoverable') or bt.get('pairable'):
        recs.append('Turn off Bluetooth discoverable/pairable when pairing is done.')
    current = wifi.get('current') or {}
    if current and int(current.get('signal') or 0) < 35:
        recs.append('Connected Wi-Fi signal is weak; move AP/Pi or use 5GHz/2.4GHz intentionally.')
    return recs or ['RF posture looks boring in the good way. Keep WPS off and passwords strong.']


def full_status() -> Dict[str, Any]:
    status = {'time': int(time.time()), 'system': system_status(), 'wifi': wifi_status(False), 'bluetooth': bluetooth_status(False), 'lan': lan_status(), 'services': service_status(), 'sensors': sensor_status(False), 'pwnagotchi_plugins': pwnagotchi_plugins(), 'security_stack': security_stack_status()}
    # Real weather is cached separately so it is actual weather again without slowing every refresh.
    status.setdefault('sensors', {})['weather'] = weather_status(status.get('sensors', {}).get('gps', {}))
    status = mark_new(status)
    status['device_memory'] = _device_memory_status(status)
    status['rf_audit'] = rf_audit_status()
    status['known_devices'] = known_devices_status(status)
    status['household_signals'] = household_signals_status(status)
    status['alert'] = _alert_status(status)
    status['gps_trail'] = _update_gps_trail(status.get('sensors', {}).get('gps', {}))
    status['status_history'] = _update_status_history(status)
    status['rf_recommendations'] = _rf_recommendations(status)
    status['log_tail'] = _recent_log_lines()
    return status
