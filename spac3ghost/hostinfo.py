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


_win_cpu_prev: Dict[str, int] = {}


def windows_cpu_percent() -> Optional[float]:
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
        prev = dict(_win_cpu_prev)
        _win_cpu_prev.update(cur)
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
