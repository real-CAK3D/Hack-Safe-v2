"""Cross-platform host metrics (stdlib only).

The Pi collectors read /proc, /sys and shell out to ``df``/``ps``. That made the
whole status payload fail on Windows/macOS. These helpers provide the same
numbers where the OS offers them and return ``None`` otherwise, so the
dashboard degrades to "n/a" per-field instead of losing everything.
"""
from __future__ import annotations

import os
import shutil
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

IS_WINDOWS = sys.platform.startswith('win')
_PROCESS_START = time.time()


def uptime_s() -> int:
    try:
        return int(float(Path('/proc/uptime').read_text().split()[0]))
    except Exception:
        pass
    if IS_WINDOWS:
        try:
            import ctypes
            return int(ctypes.windll.kernel32.GetTickCount64() // 1000)  # type: ignore[attr-defined]
        except Exception:
            pass
    return int(time.time() - _PROCESS_START)


def _fmt_bytes(n: float) -> str:
    for unit in ('B', 'K', 'M', 'G', 'T'):
        if n < 1024 or unit == 'T':
            return f'{n:.0f}{unit}' if unit in ('B', 'K') else f'{n:.1f}{unit}'
        n /= 1024
    return f'{n:.1f}T'


def memory() -> Optional[Dict[str, Any]]:
    """Memory snapshot in the same shape as the /proc/meminfo collector."""
    if not IS_WINDOWS:
        return None
    try:
        import ctypes

        class MEMSTATUS(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('sullAvailExtendedVirtual', ctypes.c_ulonglong)]
        st = MEMSTATUS()
        st.dwLength = ctypes.sizeof(MEMSTATUS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))  # type: ignore[attr-defined]
        total_mb, avail_mb = round(st.ullTotalPhys / 1048576), round(st.ullAvailPhys / 1048576)
        used_mb = max(total_mb - avail_mb, 0)
        pct = round(used_mb / total_mb * 100, 1) if total_mb else None
        swap_total = max(round((st.ullTotalPageFile - st.ullTotalPhys) / 1048576), 0)
        swap_free = max(round((st.ullAvailPageFile - st.ullAvailPhys) / 1048576), 0)
        return {
            'total_mb': total_mb, 'used_mb': used_mb, 'available_mb': avail_mb, 'free_mb': avail_mb,
            'buffers_mb': 0, 'cached_mb': 0,
            'swap_total_mb': swap_total, 'swap_used_mb': max(swap_total - swap_free, 0), 'swap_free_mb': swap_free,
            'swap_percent': round(max(swap_total - swap_free, 0) / swap_total * 100, 1) if swap_total else 0,
            'percent': pct,
            'text': f'{used_mb}/{total_mb}MB {pct}%' if pct is not None else 'n/a',
            'detail_text': f'{used_mb} MB used out of {total_mb} MB; {avail_mb} MB available',
        }
    except Exception:
        return None


_win_cpu_prev: Dict[str, Dict[str, int]] = {}


def windows_cpu_percent(key: str = 'default') -> Optional[float]:
    """CPU busy % since the previous call (first call returns None)."""
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))  # type: ignore[attr-defined]
        val = lambda ft: (ft.dwHighDateTime << 32) | ft.dwLowDateTime  # noqa: E731
        cur = {'idle': val(idle), 'total': val(kernel) + val(user)}  # kernel time includes idle
        prev = dict(_win_cpu_prev.get(key, {}))
        _win_cpu_prev[key] = cur
        if not prev:
            return None
        total = max(1, cur['total'] - prev['total'])
        return round((1 - (cur['idle'] - prev['idle']) / total) * 100, 1)
    except Exception:
        return None


def disks(limit: int = 12) -> List[Dict[str, Any]]:
    """Fixed-drive usage without shelling out to ``df``."""
    roots: List[str] = []
    if IS_WINDOWS:
        roots = [f'{c}:\\' for c in 'CDEFGHIJKLMNOPQRSTUVWXYZ' if Path(f'{c}:\\').exists()]
    else:
        roots = ['/']
    rows: List[Dict[str, Any]] = []
    for root in roots[:limit]:
        try:
            u = shutil.disk_usage(root)
        except Exception:
            continue
        pct = round(u.used / u.total * 100) if u.total else 0
        rows.append({'filesystem': root, 'size': _fmt_bytes(u.total), 'used': _fmt_bytes(u.used),
                     'avail': _fmt_bytes(u.free), 'use_percent': f'{pct}%', 'mount': root})
    return rows


def local_ips() -> List[str]:
    ips: List[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith('127.') and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


def platform_summary() -> Dict[str, Any]:
    import platform
    return {'os': platform.system() or sys.platform, 'release': platform.release(), 'machine': platform.machine(),
            'python': platform.python_version(), 'cpus': os.cpu_count() or 0}


# ---------------------------------------------------------------------------
# Windows fallbacks for the Linux-only collectors (nmcli / ip neigh / bluetoothctl / /proc/net/dev)
# ---------------------------------------------------------------------------
import re
import subprocess


def _run(cmd: List[str], timeout: int = 6) -> str:
    """Run a helper command; '' on any failure (missing tool, timeout, ...)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.stdout or ''
    except Exception:
        return ''


def net_bytes() -> Optional[Dict[str, int]]:
    """Total rx/tx byte counters across non-loopback interfaces, or None if unavailable."""
    try:
        rx = tx = 0
        for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
            if ':' not in line:
                continue
            iface, rest = line.split(':', 1)
            if iface.strip() == 'lo':
                continue
            parts = rest.split()
            if len(parts) >= 16:
                rx += int(parts[0])
                tx += int(parts[8])
        return {'rx': rx, 'tx': tx}
    except Exception:
        pass
    return None


def windows_wifi() -> Optional[List[Dict[str, Any]]]:
    """Visible Wi-Fi networks via netsh, in the same shape parse_nmcli_wifi produces."""
    if not IS_WINDOWS:
        return None
    text = _run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], 8)
    if not text.strip():
        return None
    current = None
    m = re.search(r'^\s*State\s*:\s*connected.*?^\s*SSID\s*:\s*(.+)$', _run(['netsh', 'wlan', 'show', 'interfaces'], 5), re.S | re.M)
    if m:
        current = m.group(1).strip()
    nets: Dict[str, Dict[str, Any]] = {}
    ssid = None
    security = ''
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r'SSID\s+\d+\s*:\s*(.*)$', line)
        if m:
            ssid = m.group(1).strip() or '<hidden>'
            nets.setdefault(ssid, {'connected': ssid == current, 'ssid': ssid, 'channel': '', 'signal': '0', 'security': ''})
            continue
        if ssid is None:
            continue
        rec = nets[ssid]
        m = re.match(r'Authentication\s*:\s*(.+)$', line)
        if m:
            rec['security'] = m.group(1).replace('-Personal', '').replace('-Enterprise', '-Ent').strip()
        m = re.match(r'Signal\s*:\s*(\d+)%', line)
        if m and int(m.group(1)) >= int(rec['signal']):
            rec['signal'] = m.group(1)
        m = re.match(r'Channel\s*:\s*(\d+)', line)
        if m and not rec['channel']:
            rec['channel'] = m.group(1)
    return sorted(nets.values(), key=lambda n: -int(n['signal']))


def windows_bluetooth() -> Optional[Dict[str, Any]]:
    """Paired Bluetooth devices + adapter presence via PnP."""
    if not IS_WINDOWS:
        return None
    script = ("Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
              "Select-Object Status,FriendlyName,InstanceId | ConvertTo-Json -Compress")
    raw = _run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], 12).strip()
    if not raw:
        return None
    import json
    try:
        data = json.loads(raw)
    except Exception:
        return None
    data = data if isinstance(data, list) else [data]
    devices = []
    for d in data:
        m = re.search(r'DEV_([0-9A-Fa-f]{12})', d.get('InstanceId') or '')
        if m:
            mac = ':'.join(m.group(1)[i:i + 2] for i in range(0, 12, 2)).upper()
            rec = {'mac': mac, 'name': d.get('FriendlyName') or 'Unknown', 'connected': d.get('Status') == 'OK'}
            old = next((x for x in devices if x['mac'] == mac), None)
            if old is None:
                devices.append(rec)
            elif rec['connected'] and not old['connected']:
                old.update(rec)
    adapter = any('Radio' in (d.get('FriendlyName') or '') or 'Adapter' in (d.get('FriendlyName') or '') or 'Enumerator' in (d.get('FriendlyName') or '') for d in data)
    return {'powered': adapter or bool(devices), 'devices': devices}
