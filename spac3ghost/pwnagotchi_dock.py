"""Pwnagotchi Dock.

A live dock card for a companion Pwnagotchi (e.g. CAK3DAGOTCHI), modelled on the
CYD Buddy dock. Unlike the CYD Buddy, the Pwnagotchi does not push heartbeats to
Spac3-Gh0st -- it exposes its own web UI on ``:8080``. So this module *pulls*:

- It probes a list of candidate addresses (Tailscale IP / MagicDNS name / USB
  gadget IPs) and uses whichever one answers, caching the winner.
- When reachable it reads the Pwnagotchi web UI for whatever text stats it
  exposes (name, uptime, APs/"networks seen", handshakes, mode, channel) and
  proxies the live ``/ui`` face PNG through the dashboard so the browser can show
  the face without dealing with the Pwnagotchi's own basic-auth prompt.

Secrets never live in source control. The web-UI login is read, in order, from:

1. env ``SPAC3GHOST_PWN_USER`` / ``SPAC3GHOST_PWN_PASS``
2. the git-ignored ``data/config.json`` under a ``pwnagotchi`` section
3. the stock Pwnagotchi default (``changeme`` / ``changeme``)

The address list is overridable with env ``SPAC3GHOST_PWN_HOST`` (comma
separated) or ``pwnagotchi.hosts`` in config; the port with
``SPAC3GHOST_PWN_PORT`` or ``pwnagotchi.port``.
"""
from __future__ import annotations

import base64
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:
    from .config import load_config
except Exception:  # pragma: no cover - config import is always available in app
    def load_config() -> Dict[str, Any]:
        return {}

# Default address candidates, tried in order; first to answer on the web port wins.
# The dashboard normally runs on the Hack-Safe Pi, which shares the tailnet with the
# Pwnagotchi, so the Tailscale IP is first. The MagicDNS/mDNS names survive an IP
# change, and the USB gadget IPs only work when it is cabled to *this* host.
DEFAULT_HOSTS: Tuple[str, ...] = (
    '100.100.63.24',
    'cak3dagotchi',
    'cak3dagotchi.local',
    '10.0.0.2',
    '10.66.0.2',
)
DEFAULT_PORT = 8080
DEFAULT_USER = 'changeme'
DEFAULT_PASS = 'changeme'

# TTL cache so a 15s status poll never blocks on the network: a stale read kicks a
# background probe and returns the previous snapshot immediately.
CACHE_TTL_S = 12.0
PROBE_TIMEOUT_S = 1.5

_STATE_LOCK = threading.Lock()
_STATE: Dict[str, Any] = {}
_STATE_AT = 0.0
_REFRESHING = False

# Pwnagotchi's index template exposes these as id'd spans; we grab whatever is present.
_STAT_IDS = ('name', 'status', 'channel', 'aps', 'uptime', 'shakes', 'mem', 'cpu', 'temp')
_SPAN_RE = {
    key: re.compile(r'id=["\']' + key + r'["\'][^>]*>\s*([^<]{0,120}?)\s*<', re.IGNORECASE)
    for key in _STAT_IDS
}


def _now() -> int:
    return int(time.time())


def _cfg() -> Dict[str, Any]:
    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    section = cfg.get('pwnagotchi')
    return section if isinstance(section, dict) else {}


def _hosts() -> List[str]:
    env = os.environ.get('SPAC3GHOST_PWN_HOST')
    raw: Any = env if env else (_cfg().get('hosts') or list(DEFAULT_HOSTS))
    if isinstance(raw, str):
        parts = [h.strip() for h in raw.replace(';', ',').split(',')]
    elif isinstance(raw, (list, tuple)):
        parts = [str(h).strip() for h in raw]
    else:
        parts = list(DEFAULT_HOSTS)
    hosts = [h for h in parts if h]
    return hosts or list(DEFAULT_HOSTS)


def _port() -> int:
    env = os.environ.get('SPAC3GHOST_PWN_PORT')
    try:
        return int(env) if env else int(_cfg().get('port') or DEFAULT_PORT)
    except (TypeError, ValueError):
        return DEFAULT_PORT


def _creds() -> Tuple[str, str]:
    user = os.environ.get('SPAC3GHOST_PWN_USER') or _cfg().get('username') or DEFAULT_USER
    pw = os.environ.get('SPAC3GHOST_PWN_PASS')
    if pw is None:
        pw = _cfg().get('password')
    if pw is None:
        pw = DEFAULT_PASS
    return str(user), str(pw)


def _auth_header() -> str:
    user, pw = _creds()
    token = base64.b64encode(f'{user}:{pw}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def _base_url(host: str) -> str:
    port = _port()
    suffix = '' if port == 80 else f':{port}'
    return f'http://{host}{suffix}'


def _open(host: str, path: str, timeout: float) -> Tuple[int, bytes, str]:
    """GET host+path with basic auth. Returns (status, body, content_type).

    A 401 still counts as "reachable" -- the box is up, the creds are just wrong.
    """
    url = _base_url(host) + path
    req = urllib.request.Request(url, headers={
        'Authorization': _auth_header(),
        'User-Agent': 'Spac3-Gh0st-PwnDock/1.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            ctype = resp.headers.get('Content-Type') or ''
            return resp.status, body, ctype
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read()
        except Exception:
            body = b''
        return exc.code, body, (exc.headers.get('Content-Type') if exc.headers else '') or ''


def _parse_stats(html: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, rx in _SPAN_RE.items():
        m = rx.search(html)
        if m:
            val = re.sub(r'\s+', ' ', m.group(1)).strip()
            if val:
                out[key] = val
    return out


def _probe() -> Dict[str, Any]:
    """Try each candidate host; build a status snapshot from the first that answers."""
    hosts = _hosts()
    port = _port()
    tried: List[Dict[str, Any]] = []
    for host in hosts:
        started = time.time()
        try:
            code, body, ctype = _open(host, '/', PROBE_TIMEOUT_S)
        except Exception as exc:
            tried.append({'host': host, 'ok': False, 'error': str(exc)[:120]})
            continue
        latency = int((time.time() - started) * 1000)
        reachable = True
        authed = code not in (401, 403)
        html = body.decode('utf-8', 'replace') if ('html' in ctype or not ctype) else ''
        stats = _parse_stats(html) if authed and html else {}
        name = stats.get('name') or 'CAK3DAGOTCHI'
        aps = stats.get('aps')
        snapshot = {
            'ok': True,
            'enabled': True,
            'reachable': reachable,
            'connected': reachable,
            'authed': authed,
            'host': host,
            'port': port,
            'http_code': code,
            'latency_ms': latency,
            'name': name,
            'uptime': stats.get('uptime') or '',
            'mode': (stats.get('status') or '').upper() if stats.get('status') else '',
            'channel': stats.get('channel') or '',
            'networks_seen': aps if aps is not None else '',
            'handshakes': stats.get('shakes') or '',
            'status_text': stats.get('status') or '',
            'stats': stats,
            'web_url': _base_url(host) + '/',
            'ui_url': _base_url(host) + '/ui',
            'face_proxy': '/api/pwnagotchi/ui',
            'dock_label': 'ONLINE' if authed else 'ONLINE (LOGIN NEEDED)',
            'last_seen': _now(),
            'tried': tried + [{'host': host, 'ok': True, 'http_code': code, 'latency_ms': latency}],
        }
        return snapshot
    return {
        'ok': True,
        'enabled': True,
        'reachable': False,
        'connected': False,
        'authed': False,
        'host': '',
        'port': port,
        'name': 'CAK3DAGOTCHI',
        'networks_seen': '',
        'handshakes': '',
        'uptime': '',
        'mode': '',
        'channel': '',
        'status_text': '',
        'stats': {},
        'web_url': _base_url(hosts[0]) + '/' if hosts else '',
        'ui_url': _base_url(hosts[0]) + '/ui' if hosts else '',
        'face_proxy': '/api/pwnagotchi/ui',
        'dock_label': 'OFFLINE',
        'last_seen': None,
        'tried': tried,
        'hosts': hosts,
    }


def _refresh_async() -> None:
    global _STATE, _STATE_AT, _REFRESHING
    try:
        snapshot = _probe()
    except Exception as exc:  # pragma: no cover - defensive
        snapshot = {'ok': False, 'enabled': True, 'reachable': False, 'connected': False,
                    'error': str(exc)[:160], 'dock_label': 'ERROR'}
    with _STATE_LOCK:
        _STATE = snapshot
        _STATE_AT = time.time()
        _REFRESHING = False


def pwn_dock_status() -> Dict[str, Any]:
    """Return the cached dock snapshot, refreshing in the background when stale.

    Never blocks on the network: the first-ever call returns a 'probing' stub and
    schedules a probe; later calls return the last snapshot and refresh when its
    age passes the TTL.
    """
    global _REFRESHING
    now = time.time()
    with _STATE_LOCK:
        state = dict(_STATE) if _STATE else {}
        age = now - _STATE_AT if _STATE_AT else None
        stale = (not _STATE) or (age is not None and age >= CACHE_TTL_S)
        should_refresh = stale and not _REFRESHING
        if should_refresh:
            _REFRESHING = True
    if should_refresh:
        threading.Thread(target=_refresh_async, name='pwn-dock-refresh', daemon=True).start()
    if not state:
        return {
            'ok': True, 'enabled': True, 'reachable': False, 'connected': False,
            'authed': False, 'name': 'CAK3DAGOTCHI', 'networks_seen': '', 'handshakes': '',
            'uptime': '', 'mode': '', 'channel': '', 'status_text': '', 'stats': {},
            'face_proxy': '/api/pwnagotchi/ui', 'dock_label': 'PROBING',
            'hosts': _hosts(), 'last_seen': None,
        }
    state['age_s'] = int(age) if age is not None else None
    return state


def fetch_ui_png() -> Tuple[Optional[bytes], str, int]:
    """Fetch the live face PNG from the current working host (or probe for one).

    Returns (body_or_None, content_type, http_code). On any failure returns
    (None, error_string, code).
    """
    with _STATE_LOCK:
        host = (_STATE or {}).get('host') or ''
    candidates = [host] if host else []
    for h in _hosts():
        if h not in candidates:
            candidates.append(h)
    last_code = 502
    for h in candidates:
        if not h:
            continue
        try:
            code, body, ctype = _open(h, '/ui', PROBE_TIMEOUT_S + 1.0)
        except Exception:
            continue
        if code == 200 and body:
            return body, (ctype or 'image/png'), 200
        last_code = code
    return None, f'pwnagotchi face unavailable (last http {last_code})', last_code
