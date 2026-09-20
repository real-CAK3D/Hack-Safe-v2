"""Rolling in-memory telemetry for the live charts.

A daemon thread samples cheap host metrics every couple of seconds so charts
have history the moment a browser connects (instead of starting empty and only
growing while the tab is open). Nothing is written to disk.
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from . import hostinfo

INTERVAL_S = 2.0
MAX_SAMPLES = 1800  # 1 hour at 2 s

_lock = threading.Lock()
_samples: Deque[Dict[str, Any]] = deque(maxlen=MAX_SAMPLES)
_thread: Optional[threading.Thread] = None
_prev_net: Optional[Dict[str, Any]] = None
_prev_proc_stat: Optional[List[int]] = None


def _cpu_percent() -> Optional[float]:
    global _prev_proc_stat
    try:
        vals = [int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
        prev, _prev_proc_stat = _prev_proc_stat, vals
        if not prev:
            return None
        idle_d = (vals[3] + (vals[4] if len(vals) > 4 else 0)) - (prev[3] + (prev[4] if len(prev) > 4 else 0))
        total_d = max(1, sum(vals) - sum(prev))
        return round((1 - idle_d / total_d) * 100, 1)
    except Exception:
        return hostinfo.windows_cpu_percent('metrics')


def _memory_percent() -> Optional[float]:
    try:
        info = {}
        for line in Path('/proc/meminfo').read_text().splitlines():
            k, v = line.split(':', 1)
            info[k] = int(v.strip().split()[0])
        total = info.get('MemTotal', 0)
        return round((total - info.get('MemAvailable', 0)) / total * 100, 1) if total else None
    except Exception:
        mem = hostinfo.memory()
        return mem.get('percent') if mem else None


def _disk_percent() -> Optional[float]:
    try:
        root = 'C:\\' if hostinfo.IS_WINDOWS else '/'
        u = shutil.disk_usage(root)
        return round(u.used / u.total * 100, 1) if u.total else None
    except Exception:
        return None


def _temp_c() -> Optional[float]:
    try:
        return round(int(Path('/sys/class/thermal/thermal_zone0/temp').read_text().strip()) / 1000.0, 1)
    except Exception:
        return None


def sample() -> Dict[str, Any]:
    """Take one sample (also used directly by tests)."""
    global _prev_net
    now = time.time()
    rx_bps = tx_bps = None
    counters = hostinfo.net_bytes()
    if counters:
        if _prev_net:
            dt = max(0.001, now - _prev_net['t'])
            rx_bps = max(0.0, round((counters['rx'] - _prev_net['rx']) / dt, 1))
            tx_bps = max(0.0, round((counters['tx'] - _prev_net['tx']) / dt, 1))
        _prev_net = {'t': now, **counters}
    load = None
    try:
        load = round(os.getloadavg()[0], 2)
    except Exception:
        pass
    return {'t': round(now, 2), 'cpu': _cpu_percent(), 'mem': _memory_percent(), 'disk': _disk_percent(),
            'temp': _temp_c(), 'rx': rx_bps, 'tx': tx_bps, 'load': load}


def _loop() -> None:
    while True:
        try:
            s = sample()
            with _lock:
                _samples.append(s)
        except Exception:
            pass
        time.sleep(INTERVAL_S)


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, name='spac3-metrics', daemon=True)
    _thread.start()


def history(since: float = 0.0, limit: int = 900) -> Dict[str, Any]:
    start()
    with _lock:
        rows = [s for s in _samples if s['t'] > since]
    return {'interval': INTERVAL_S, 'now': round(time.time(), 2), 'samples': rows[-limit:]}
