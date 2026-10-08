"""NeuroLab status collector (stdlib only, read-only).

NeuroLab is the Docker-hosted facility/telemetry simulation on the NukeBox. It exposes a
compact rollup at ``<url>/api/summary``; this module fetches it for the Systems-tab card.
The last good payload is kept so a brief tailnet blip shows "stale" instead of an empty card.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict

from .config import load_config

DEFAULT_URL = 'https://nukebox.tailac984b.ts.net:10000'
CACHE_TTL_S = 15
TIMEOUT_S = 4

_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {'at': 0.0, 'url': '', 'value': None, 'last_good': None, 'last_good_at': 0.0}


def neurolab_url() -> str:
    cfg = (load_config().get('neurolab') or {})
    return str(os.environ.get('SPAC3GHOST_NEUROLAB_URL') or cfg.get('url') or DEFAULT_URL).rstrip('/')


def _fetch(url: str) -> Dict[str, Any]:
    started = time.time()
    req = urllib.request.Request(f'{url}/api/summary', headers={'Accept': 'application/json', 'User-Agent': 'spac3ghost'})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = json.loads(resp.read(512 * 1024).decode('utf-8'))
    if not isinstance(data, dict):
        raise ValueError('unexpected summary payload')
    data['latency_ms'] = int((time.time() - started) * 1000)
    return data


def neurolab_status(force: bool = False) -> Dict[str, Any]:
    cfg = (load_config().get('neurolab') or {})
    if cfg.get('enabled') is False:
        return {'available': False, 'enabled': False, 'error': 'disabled in config'}
    url = neurolab_url()
    now = time.time()
    with _LOCK:
        if not force and _CACHE['value'] is not None and _CACHE['url'] == url and now - _CACHE['at'] < CACHE_TTL_S:
            return _CACHE['value']
    try:
        summary = _fetch(url)
        result: Dict[str, Any] = {'available': True, 'stale': False, 'url': url, 'summary': summary}
        with _LOCK:
            _CACHE['last_good'], _CACHE['last_good_at'] = result, now
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        reason = getattr(exc, 'reason', exc)
        with _LOCK:
            last_good, last_at = _CACHE['last_good'], _CACHE['last_good_at']
        if last_good and last_good.get('url') == url:
            result = {**last_good, 'stale': True, 'error': str(reason), 'age_s': int(now - last_at)}
        else:
            result = {'available': False, 'stale': False, 'url': url, 'error': str(reason)}
    with _LOCK:
        _CACHE.update(at=now, url=url, value=result)
    return result


_REFRESHING = threading.Event()


def _refresh_bg() -> None:
    try:
        neurolab_status(force=True)
    except Exception:
        pass
    finally:
        _REFRESHING.clear()


def neurolab_snapshot() -> Dict[str, Any]:
    """Non-blocking status: returns the cached/last-good value immediately and refreshes in the background."""
    try:
        cfg = (load_config().get('neurolab') or {})
        if cfg.get('enabled') is False:
            return {'available': False, 'enabled': False, 'error': 'disabled in config'}
        url = neurolab_url()
        with _LOCK:
            value, at, cached_url = _CACHE['value'], _CACHE['at'], _CACHE['url']
        if value is None or cached_url != url:
            value = None
        if (value is None or time.time() - at >= CACHE_TTL_S) and not _REFRESHING.is_set():
            _REFRESHING.set()
            threading.Thread(target=_refresh_bg, daemon=True).start()
        return value or {'available': False, 'pending': True, 'url': url, 'error': 'checking'}
    except Exception as exc:
        return {'available': False, 'error': str(exc)}


def neurolab_role(snap: Dict[str, Any]) -> str:
    """One-line live-state string for the Household Signals entry."""
    base = 'facility telemetry sim'
    if snap.get('enabled') is False:
        return f'{base} // disabled'
    if snap.get('pending'):
        return f'{base} // checking'
    if not snap.get('available'):
        return f'{base} // offline'
    s = snap.get('summary') or {}
    svcs = s.get('services') or []
    tel = s.get('telemetry') or {}
    parts = ['stale' if snap.get('stale') else 'online']
    if s.get('tick') is not None:
        parts.append(f"tick {s['tick']}")
    if svcs:
        parts.append(f"{sum(1 for x in svcs if x.get('ok'))}/{len(svcs)} services")
    if tel.get('total') is not None:
        parts.append(f"telemetry {tel.get('online', 0)}/{tel['total']}")
    return f'{base} // ' + ' · '.join(parts)


def neurolab_state(snap: Dict[str, Any]) -> str:
    if snap.get('enabled') is False or snap.get('pending'):
        return 'unknown'
    if not snap.get('available'):
        return 'offline'
    return 'stale' if snap.get('stale') else 'online'
