from __future__ import annotations

import json
import mimetypes
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .collectors import active_recon, bluetooth_status, calibrate_tilt_level, full_status, handshake_capture_status, known_devices_status, known_wifi_passwords, lan_status, meshtastic_status, monitor_mode_status, pwnagotchi_plugins, sensor_status, set_monitor_mode, start_owned_lab_capture, stop_owned_lab_capture, tilt_status, update_known_device, weather_tile_url, wifi_psk_action, wifi_status, wifi_target_action
from . import __version__, hostinfo, metrics
from .config import load_config, save_config
from .controls import ai_chat_ask, ai_chat_status, camera_status, external_control, external_status, ir_action, launch_proton_gui, service_status, services_status, set_camera_feed, set_vision_enabled, spicy_tool_action, spicy_tools_status, lab_toys_status, companion_firmware_action, flipper_feature_action, lab_gate_action, nfc_rfid_action, safety_boundary_action, lab_software_action, tailscale_ip, tailscale_status, tailscale_up, tailscale_restart, tailscale_protect, toggle_service, toggle_vpn, vpn_status, select_vpn_profile, connect_vpn_profile
from .cyd import cyd_settings, cyd_status, record_heartbeat, telemetry_from_status, update_cyd_settings
from .personality import Spac3Voice, choose_mood, event_from_status, merged_faces
from .paths import ROOT, WEB_DIR
from .plugins import PluginManager
from .vision import SNAP_DIR, analyze_current_frame, clear_vision_history, jpeg_frame, vision_history

WEB = WEB_DIR
EVENTS = []
LAST_CHATTER = 0
LAST_PLUGIN_PANELS = []
VOICE = Spac3Voice()
PLUGINS = PluginManager()
STATUS_CACHE = {}
STATUS_CACHE_AT = 0.0
STATUS_REFRESHING = False
STATUS_CACHE_LOCK = threading.Lock()
STATUS_TTL = 20
STATUS_COLD_WAIT = 2.0


STARTED_AT = time.time()


def health_payload():
    """Cheap liveness probe: never touches slow collectors."""
    plugins = PLUGINS.describe()
    return {
        'ok': True,
        'version': __version__,
        'uptime_s': int(time.time() - STARTED_AT),
        'host_uptime_s': hostinfo.uptime_s(),
        'platform': hostinfo.platform_summary(),
        'plugins': {'loaded': sum(1 for p in plugins if p.get('loaded')), 'enabled': sum(1 for p in plugins if p.get('enabled')), 'total': len(plugins)},
        'status_cache_age_s': round(time.time() - STATUS_CACHE_AT, 1) if STATUS_CACHE_AT else None,
    }


def add_event(kind: str, text: str):
    event = {'ts': int(time.time()), 'kind': kind, 'text': text}
    EVENTS.append(event)
    del EVENTS[:-80]
    return event


def json_response(handler, payload, code=200):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(data)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(data)


def binary_response(handler, body: bytes, content_type: str, code=200):
    handler.send_response(code)
    handler.send_header('Content-Type', content_type)
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(body)



GODSEYE_LIVE_ORIGIN = 'http://127.0.0.1:4173'
GODSEYE_API_PREFIXES = (
    '/api/cctv', '/api/opensky', '/api/opensky-track', '/api/tomtom',
    '/api/adsblol', '/api/ais-live', '/api/google', '/api/regional-brief',
    '/api/cache', '/api/eonet', '/api/earthquakes', '/api/iss', '/api/satellites',
    '/api/radio', '/api/firms', '/api/celestrak', '/api/launches', '/api/gbfs',
    # God’s Eye Vite proxy APIs used by OSM/Google/traffic/annotation layers.
    # These include POST endpoints, so proxy_godseye must preserve method/body.
    '/api/overpass', '/api/route', '/api/terrain/heights', '/api/adsbdb'
)
GODSEYE_DEV_PREFIXES = ('/@vite/', '/src/', '/node_modules/', '/cesium/', '/pin.svg', '/location.svg', '/visual-presets.svg')


def proxy_godseye(handler, upstream_path: str, rewrite_html: bool = False):
    """Proxy Gods Eye live Vite/API traffic through Spac3-Gh0st on :8765.

    God’s Eye uses POST APIs such as /api/overpass for OpenStreetMap /
    traffic / annotation geometry. Preserve method, body, and content-type so
    the dashboard proxy behaves like the live Vite backend instead of turning
    OSM requests into 404/empty GETs.
    """
    url = GODSEYE_LIVE_ORIGIN + upstream_path
    if getattr(handler, '_godseye_query', ''):
        url += '?' + handler._godseye_query
    method = getattr(handler, 'command', 'GET') or 'GET'
    body = None
    if method in ('POST', 'PUT', 'PATCH'):
        length = int(handler.headers.get('Content-Length') or 0)
        body = handler.rfile.read(length) if length > 0 else b''
    headers = {'User-Agent': 'Spac3-Gh0st-GodsEyeProxy/1.0'}
    accept = handler.headers.get('Accept')
    if accept:
        headers['Accept'] = accept
    content_type = handler.headers.get('Content-Type')
    if content_type:
        headers['Content-Type'] = content_type
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=150 if upstream_path.startswith('/api/firms') else 45) as resp:
            body = resp.read()
            content_type = resp.headers.get('Content-Type') or mimetypes.guess_type(upstream_path)[0] or 'application/octet-stream'
            if rewrite_html and 'text/html' in content_type:
                text = body.decode('utf-8', 'replace')
                rewrites = {
                    'src="/@vite/': 'src="/godseye-live/@vite/',
                    'src="/src/': 'src="/godseye-live/src/',
                    'src="/node_modules/': 'src="/godseye-live/node_modules/',
                    'href="/cesium/': 'href="/godseye-live/cesium/',
                    'src="/cesium/': 'src="/godseye-live/cesium/',
                    'href="/style.css"': 'href="/godseye-live/style.css"',
                    'src="/style.css"': 'src="/godseye-live/style.css"',
                }
                for old, new in rewrites.items():
                    text = text.replace(old, new)
                body = text.encode('utf-8')
                content_type = 'text/html; charset=utf-8'
            handler.send_response(resp.status)
            handler.send_header('Content-Type', content_type)
            handler.send_header('Content-Length', str(len(body)))
            handler.send_header('Cache-Control', 'no-store')
            handler.end_headers()
            handler.wfile.write(body)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read()
        except Exception:
            body = str(exc).encode('utf-8')
        handler.send_response(exc.code)
        handler.send_header('Content-Type', exc.headers.get('Content-Type') or 'text/plain; charset=utf-8')
        handler.send_header('Content-Length', str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except Exception as exc:
        json_response(handler, {'ok': False, 'error': f'Gods Eye proxy failed: {exc}'}, code=502)

def _hostname_of(value: str) -> str:
    value = (value or '').strip().lower()
    if value.startswith('['):  # [::1]:8765
        return value[1:].split(']', 1)[0]
    return value.rsplit(':', 1)[0] if value.count(':') == 1 else value


def _host_allowed(host_header: str) -> bool:
    """Allow only hosts a legitimate dashboard user would type. Blocks DNS-rebinding pages."""
    import ipaddress
    import socket
    name = _hostname_of(host_header)
    if not name:
        return False
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        pass
    extra = {h.strip().lower() for h in os.environ.get('SPAC3GHOST_ALLOWED_HOSTS', '').split(',') if h.strip()}
    own = {socket.gethostname().lower(), 'localhost'}
    return name in own or name in extra or '.' not in name or name.endswith(('.ts.net', '.local', '.lan', '.home.arpa'))


def check_request(headers, method: str = 'GET'):
    """Return an error string if the request should be refused, else None.

    The dashboard has powerful unauthenticated POST endpoints (VPN, services, config, lab
    actions). Without this, any web page you visit could fire requests at
    http://127.0.0.1:8765 or your tailnet address (CSRF), or rebind a hostname to it.
    """
    if not _host_allowed(headers.get('Host', '')):
        return 'unexpected Host header (set SPAC3GHOST_ALLOWED_HOSTS to allow it)'
    if (headers.get('Sec-Fetch-Site') or '').lower() == 'cross-site':
        return 'cross-site request blocked'
    origin = headers.get('Origin')
    if origin and origin.lower() != 'null':
        if urlparse(origin).netloc.lower() != (headers.get('Host') or '').lower():
            return 'cross-origin request blocked'
    elif origin and origin.lower() == 'null' and method != 'GET':
        return 'opaque-origin request blocked'
    return None


def read_json_body(handler):
    length = int(handler.headers.get('Content-Length') or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode('utf-8'))


def _clone_payload(payload):
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _minimal_status(reason='warming'):
    config = load_config()
    status = {
        'time': int(time.time()),
        'cache_state': reason,
        'status_latency_ms': 0,
        'system': {},
        'wifi': {},
        'bluetooth': {},
        'lan': {},
        'services': {},
        'sensors': {},
        'pwnagotchi_plugins': {},
        'security_stack': {},
        'device_memory': {},
        'rf_audit': {},
        'known_devices': {},
        'gps_trail': {},
        'status_history': {},
        'rf_recommendations': [],
        'log_tail': [],
        'vpn': {},
        'tailscale': {},
        'vision': {},
        'vision_history': {},
        'controls': {},
        'spicy_tools': {},
        'lab_toys': {},
        'externals': {},
        'cyd_buddy': cyd_status(),
        'tailscale_url': '',
        'native_plugins': PLUGINS.describe(),
        'plugin_panels': list(LAST_PLUGIN_PANELS),
        'config': config,
        'faces': merged_faces(),
        'events': list(reversed(EVENTS[-30:])),
    }
    status['mood'] = {'name': 'WARMING', 'face': '(@-@)', 'color': '#f2d35c'}
    status['thought'] = 'Warming slow telemetry cache. Dashboard is awake; heavy sensors are loading in the background.'
    return status


def _collect_status_payload():
    collectors = {
        'base': full_status,
        'vpn': vpn_status,
        'tailscale': tailscale_status,
        'vision': camera_status,
        'vision_history': lambda: vision_history(8),
        'controls': services_status,
        'spicy_tools': spicy_tools_status,
        'lab_toys': lab_toys_status,
        'externals': external_status,
        'tailscale_ip': tailscale_ip,
    }
    started = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): key for key, fn in collectors.items()}
        for fut, key in ((f, futures[f]) for f in futures):
            try:
                results[key] = fut.result(timeout=7)
            except Exception as exc:
                results[key] = {'available': False, 'error': str(exc)}
    status = results.pop('base') if isinstance(results.get('base'), dict) else {'time': int(time.time()), 'error': results.get('base')}
    for key in ('vpn', 'tailscale', 'vision', 'vision_history', 'controls', 'spicy_tools', 'lab_toys', 'externals'):
        status[key] = results.get(key)
    status['cyd_buddy'] = cyd_status()
    ts_url = os.environ.get('SPAC3GHOST_TAILSCALE_URL') or load_config().get('tailscale', {}).get('url') or ''
    status['tailscale_url'] = ts_url if results.get('tailscale_ip') else ''
    status['collector_latency_ms'] = int((time.time() - started) * 1000)
    status['native_plugins'] = PLUGINS.describe()
    mood = choose_mood(status)
    status['mood'] = mood
    status['thought'] = event_from_status(status)['text']
    global LAST_CHATTER
    if time.time() - LAST_CHATTER >= 8:
        add_event('chatter', VOICE.chatter(status))
        LAST_CHATTER = time.time()
    status['events'] = list(reversed(EVENTS[-30:]))
    global LAST_PLUGIN_PANELS
    panels = [p for p in PLUGINS.call('on_status', status) if isinstance(p, dict)]
    LAST_PLUGIN_PANELS = panels
    status['plugin_panels'] = list(LAST_PLUGIN_PANELS)
    status['config'] = load_config()
    status['faces'] = merged_faces()
    status['cache_state'] = 'fresh'
    return status


def _refresh_status_cache():
    global STATUS_CACHE, STATUS_CACHE_AT, STATUS_REFRESHING
    with STATUS_CACHE_LOCK:
        if STATUS_REFRESHING:
            return
        STATUS_REFRESHING = True
    try:
        payload = _collect_status_payload()
        with STATUS_CACHE_LOCK:
            STATUS_CACHE = payload
            STATUS_CACHE_AT = time.time()
    except Exception as exc:
        add_event('status', f'Status cache refresh failed: {exc}')
    finally:
        with STATUS_CACHE_LOCK:
            STATUS_REFRESHING = False


def _trigger_status_refresh(force=False):
    with STATUS_CACHE_LOCK:
        age = time.time() - STATUS_CACHE_AT if STATUS_CACHE_AT else 999999
        should = force or not STATUS_CACHE or (age >= STATUS_TTL)
        running = STATUS_REFRESHING
    if should and not running:
        threading.Thread(target=_refresh_status_cache, daemon=True).start()


def status_snapshot(force=False, wait=False):
    started = time.time()
    if force:
        _refresh_status_cache()
    else:
        _trigger_status_refresh(False)
    deadline = time.time() + (STATUS_COLD_WAIT if wait else 0)
    while wait and time.time() < deadline:
        with STATUS_CACHE_LOCK:
            if STATUS_CACHE:
                break
        time.sleep(0.05)
    with STATUS_CACHE_LOCK:
        payload = _clone_payload(STATUS_CACHE) if STATUS_CACHE else _minimal_status('warming')
        cache_at = STATUS_CACHE_AT
        refreshing = STATUS_REFRESHING
    payload['cache_age_s'] = round(time.time() - cache_at, 1) if cache_at else None
    payload['cache_refreshing'] = bool(refreshing)
    payload['status_latency_ms'] = int((time.time() - started) * 1000)
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = 'Spac3-Gh0st/0.2'

    def _safely(self, fn):
        try:
            return fn()
        except (BrokenPipeError, ConnectionResetError):
            return None
        except Exception as exc:  # noqa: BLE001 - last-resort net so the UI gets an answer
            sys.stderr.write('[%s] handler error on %s: %r\n' % (time.strftime('%H:%M:%S'), self.path, exc))
            try:
                return json_response(self, {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}, code=500)
            except Exception:
                return None

    def do_GET(self):
        return self._safely(self._do_get)

    def do_POST(self):
        return self._safely(self._do_post)

    def _do_get(self):
        parsed = urlparse(self.path)
        path = parsed.path
        self._godseye_query = parsed.query
        if path == '/godseye-live' or path == '/godseye-live/':
            return proxy_godseye(self, '/', rewrite_html=True)
        if path.startswith('/godseye-live/'):
            return proxy_godseye(self, path.removeprefix('/godseye-live'), rewrite_html=path.endswith('.html'))
        if path.startswith(GODSEYE_API_PREFIXES):
            return proxy_godseye(self, path)
        if path.startswith(GODSEYE_DEV_PREFIXES):
            return proxy_godseye(self, path)
        if path.startswith('/api/'):
            problem = check_request(self.headers, 'GET')
            if problem:
                return json_response(self, {'ok': False, 'error': problem}, code=403)
        if path == '/api/status':
            return json_response(self, status_snapshot(wait=False))
        if path == '/api/cyd/status':
            return json_response(self, cyd_status())
        if path == '/api/cyd/settings':
            return json_response(self, cyd_settings())
        if path == '/api/cyd/telemetry':
            return json_response(self, telemetry_from_status(status_snapshot(wait=False)))
        if path == '/api/mesh/status':
            return json_response(self, {'meshtastic': meshtastic_status(force=parsed.query in ('force=1', 'refresh=1'))})
        if path == '/api/health':
            return json_response(self, health_payload())
        if path == '/api/metrics':
            q = parse_qs(parsed.query)
            try:
                since = float((q.get('since') or ['0'])[0])
                limit = max(1, min(1800, int((q.get('limit') or ['900'])[0])))
            except ValueError:
                since, limit = 0.0, 900
            return json_response(self, metrics.history(since, limit))
        if path == '/api/status/slow':
            force = parsed.query in ('force=1', 'refresh=1')
            return json_response(self, status_snapshot(force=force, wait=True))
        if path == '/api/config':
            return json_response(self, {'config': load_config(), 'faces': merged_faces(), 'plugins': PLUGINS.describe()})
        if path == '/api/scan/wifi':
            data = wifi_status(True)
            add_event('wifi', VOICE.wifi_scan(len(data.get('networks', []))))
            PLUGINS.call('on_wifi_scan', data)
            return json_response(self, data)
        if path == '/api/scan/bluetooth':
            data = bluetooth_status(True)
            add_event('bluetooth', VOICE.bluetooth_scan(len(data.get('devices', []))))
            PLUGINS.call('on_bluetooth_scan', data)
            return json_response(self, data)
        if path == '/api/scan/lan':
            data = lan_status()
            add_event('lan', VOICE.lan_scan(len(data.get('devices', []))))
            PLUGINS.call('on_lan_scan', data)
            return json_response(self, data)
        if path == '/api/sensors/refresh':
            data = sensor_status(True)
            add_event('sensors', VOICE.sensors_refreshed())
            return json_response(self, data)
        if path == '/api/sensors/tilt':
            return json_response(self, tilt_status())
        if path == '/api/wifi/passwords':
            reveal = parsed.query in ('reveal=1', 'show=1')
            add_event('wifi', 'Known Wi-Fi vault opened.' if reveal else 'Known Wi-Fi vault listed.')
            return json_response(self, known_wifi_passwords(reveal))
        if path == '/api/vpn/status':
            return json_response(self, vpn_status())
        if path == '/api/tailscale/status':
            return json_response(self, tailscale_status())
        if path == '/api/camera/status':
            return json_response(self, camera_status())
        if path == '/api/vision/history':
            return json_response(self, vision_history())
        if path.startswith('/api/camera/snapshot/'):
            name = Path(path).name
            snap = (SNAP_DIR / name).resolve()
            if str(snap).startswith(str(SNAP_DIR.resolve())) and snap.exists():
                return binary_response(self, snap.read_bytes(), 'image/jpeg')
            return json_response(self, {'ok': False, 'error': 'snapshot not found'}, code=404)
        if path == '/api/known-devices':
            return json_response(self, known_devices_status())
        if path == '/api/camera/frame':
            try:
                feed_id = (parse_qs(parsed.query).get('feed') or [None])[0]
                body, content_type = jpeg_frame(with_detections=True, feed_id=feed_id)
                return binary_response(self, body, content_type)
            except Exception as exc:
                return json_response(self, {'ok': False, 'error': str(exc)}, code=500)
        if path.startswith('/api/weather/tile/') and path.endswith('.png'):
            try:
                parts = path.removeprefix('/api/weather/tile/').removesuffix('.png').split('/')
                if len(parts) != 4:
                    raise ValueError('expected /api/weather/tile/{layer}/{z}/{x}/{y}.png')
                body, content_type = weather_tile_url(parts[0], parts[1], parts[2], parts[3])
                return binary_response(self, body, content_type)
            except Exception as exc:
                return json_response(self, {'ok': False, 'error': str(exc)}, code=400)
        if path == '/api/services/status':
            return json_response(self, services_status())
        if path == '/api/spicy/status':
            return json_response(self, spicy_tools_status())
        if path == '/api/lab/status':
            return json_response(self, lab_toys_status())
        if path == '/api/externals/status':
            return json_response(self, external_status())
        if path == '/api/ai/chat':
            return json_response(self, ai_chat_status())
        if path == '/api/plugins/pwnagotchi':
            return json_response(self, {'plugins': pwnagotchi_plugins()})
        if path == '/api/pwnagotchi/monitor':
            return json_response(self, set_monitor_mode('status'))
        if path == '/api/pwnagotchi/capture':
            return json_response(self, handshake_capture_status())
        if path == '/api/pwnagotchi/captures':
            return json_response(self, handshake_capture_status())
        if path == '/api/events':
            return json_response(self, {'events': list(reversed(EVENTS[-80:]))})
        if path == '/':
            path = '/index.html'
        file_path = (WEB / path.lstrip('/')).resolve()
        if file_path.is_dir():
            index_path = (file_path / 'index.html').resolve()
            if str(index_path).startswith(str(WEB.resolve())) and index_path.exists():
                file_path = index_path
        if not str(file_path).startswith(str(WEB.resolve())) or not file_path.exists() or file_path.is_dir():
            self.send_error(404)
            return
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        if path.startswith('/godseye-app/') or path in ('/app.js', '/style.css'):
            self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _do_post(self):
        parsed = urlparse(self.path)
        path = parsed.path
        self._godseye_query = parsed.query
        problem = check_request(self.headers, 'POST')
        if problem:
            return json_response(self, {'ok': False, 'error': problem}, code=403)
        if path.startswith(GODSEYE_API_PREFIXES):
            return proxy_godseye(self, path)
        if path == '/api/config':
            try:
                config = save_config(read_json_body(self).get('config', {}))
                global VOICE
                VOICE = Spac3Voice()
                PLUGINS.reload()
                add_event('settings', VOICE.settings_saved())
                return json_response(self, {'ok': True, 'config': config, 'plugins': PLUGINS.describe()})
            except Exception as exc:
                return json_response(self, {'ok': False, 'error': str(exc)}, code=400)
        if path == '/api/cyd/heartbeat':
            result = record_heartbeat(read_json_body(self), self.client_address[0] if self.client_address else '')
            add_event('cyd', f"CYD Buddy heartbeat from {result.get('buddy', {}).get('ip') or 'unknown'}")
            _trigger_status_refresh(force=True)
            return json_response(self, result)
        if path == '/api/cyd/settings':
            body = read_json_body(self)
            result = update_cyd_settings(body)
            menu = result.get('active_menu') or body.get('menu') or 'settings'
            add_event('cyd', result.get('error') or f"CYD Buddy settings command queued: {menu}")
            _trigger_status_refresh(force=True)
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/vpn/toggle':
            result = toggle_vpn()
            add_event('vpn', result.get('message') or result.get('error') or VOICE.vpn_result(result.get('action', 'toggle')))
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/vpn/open':
            result = launch_proton_gui()
            add_event('vpn', result.get('message') or result.get('error') or 'Hack-Safe VPN GUI launch requested.')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/vpn/select':
            body = read_json_body(self)
            result = select_vpn_profile(body.get('profile') or body.get('country') or body.get('name'))
            add_event('vpn', result.get('message') or result.get('error') or 'VPN profile selection requested.')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/vpn/connect':
            body = read_json_body(self)
            result = connect_vpn_profile(body.get('profile') or body.get('country') or body.get('name'))
            add_event('vpn', result.get('message') or result.get('error') or 'VPN connect requested.')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/tailscale/up':
            result = tailscale_up()
            add_event('tailscale', result.get('message') or result.get('stderr') or 'Tailscale up requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/tailscale/restart':
            result = tailscale_restart()
            add_event('tailscale', result.get('message') or result.get('stderr') or 'Tailscale restart requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/tailscale/protect':
            result = tailscale_protect()
            add_event('tailscale', result.get('message') or result.get('stderr') or 'Tailscale route protection requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/spicy/action':
            body = read_json_body(self)
            result = spicy_tool_action(body.get('tool'), body.get('action'))
            add_event('spicy', result.get('message') or result.get('error') or 'spicy tool action requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/lab/flipper/action':
            body = read_json_body(self)
            result = flipper_feature_action(body.get('feature'), body.get('action'))
            add_event('lab', result.get('message') or result.get('error') or 'Flipper-inspired feature toggle requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/lab/companion/action':
            body = read_json_body(self)
            result = companion_firmware_action(body.get('companion'), body.get('action'))
            add_event('lab', result.get('message') or result.get('error') or 'Companion firmware action requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/lab/gate/action':
            body = read_json_body(self)
            result = lab_gate_action(body.get('gate'), body.get('action'))
            add_event('lab', result.get('message') or result.get('error') or 'Blocked lab module gate requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/lab/nfc-rfid/action':
            body = read_json_body(self)
            result = nfc_rfid_action(str(body.get('action') or ''), str(body.get('text') or ''), bool(body.get('owned_blank')))
            add_event('lab', result.get('message') or result.get('error') or 'NFC/RFID action requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/lab/ir/action':
            body = read_json_body(self)
            result = ir_action(str(body.get('action') or ''))
            add_event('lab', result.get('message') or result.get('error') or 'IR action requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/lab/safety-boundary/action':
            body = read_json_body(self)
            result = safety_boundary_action(body.get('boundary'), body.get('action'))
            add_event('lab', result.get('message') or result.get('error') or 'Safety boundary toggle requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/lab/software/action':
            body = read_json_body(self)
            result = lab_software_action(body.get('module'), body.get('action'))
            add_event('lab', result.get('message') or result.get('error') or 'Lab software action requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/camera/vision':
            try:
                body = read_json_body(self)
                result = set_vision_enabled(bool(body.get('enabled')))
                VOICE = Spac3Voice()
                add_event('camera', VOICE.vision_toggle(bool(result.get('enabled'))))
                return json_response(self, result)
            except Exception as exc:
                return json_response(self, {'ok': False, 'error': str(exc)}, code=400)
        if path == '/api/camera/feed':
            body = read_json_body(self)
            result = set_camera_feed(str(body.get('feed') or body.get('feed_id') or ''))
            if result.get('ok'):
                add_event('camera', f"Camera feed switched to {result.get('active_feed')}")
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/vision/history/clear':
            result = clear_vision_history()
            add_event('camera', f"Vision history cleared: {result.get('removed_rows', 0)} rows / {result.get('removed_snapshots', 0)} snapshots removed.")
            return json_response(self, result)
        if path == '/api/sensors/tilt/calibrate':
            body = read_json_body(self)
            raw = body.get('raw') if 'raw' in body else None
            result = calibrate_tilt_level(raw)
            if result.get('ok'):
                add_event('sensors', result.get('message', 'Tilt calibrated.'))
                _trigger_status_refresh(force=True)
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/camera/analyze':
            body = read_json_body(self)
            result = analyze_current_frame(feed_id=str(body.get('feed') or body.get('feed_id') or ''))
            labels = [d.get('label', 'object') for d in result.get('detections', [])[:4]]
            add_event('camera', VOICE.yolo_result(labels, result.get('error') or ''))
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/pwnagotchi/capture':
            body = read_json_body(self)
            action = str(body.get('action') or 'start').lower()
            if action in ('monitor', 'prep-monitor', 'enable-monitor'):
                result = set_monitor_mode('enable', str(body.get('interface') or ''))
                add_event('pwnagotchi', result.get('message') or result.get('error') or 'Monitor-mode prep requested for USB Wi-Fi dongle')
                return json_response(self, result, code=200 if result.get('ok') else 400)
            if action in ('stop-monitor', 'disable-monitor'):
                result = set_monitor_mode('disable', str(body.get('interface') or ''))
                add_event('pwnagotchi', result.get('message') or result.get('error') or 'Monitor-mode stop requested for USB Wi-Fi dongle')
                return json_response(self, result, code=200 if result.get('ok') else 400)
            if action == 'stop':
                result = stop_owned_lab_capture()
                add_event('pwnagotchi', f"Owned-lab passive capture stop requested: {'stopped' if result.get('stopped') else result.get('message') or result.get('error', 'unknown')}")
                return json_response(self, result, code=200 if result.get('ok') else 400)
            if action not in ('start', ''):
                return json_response(self, {'ok': False, 'error': 'unsupported capture action'}, code=400)
            result = start_owned_lab_capture(body)
            if result.get('ok'):
                add_event('pwnagotchi', f"Owned-lab passive capture started on {body.get('interface') or 'monitor adapter'} pid {result.get('pid')} -- no deauth, no cracking.")
            else:
                add_event('pwnagotchi', f"Capture refused: {result.get('error', 'unknown error')}")
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/recon/aggressive':
            result = active_recon()
            if result.get('ok'):
                add_event('recon', f"Active local recon swept {result.get('scope')} and found {result.get('host_count', 0)} live hosts. No deauth, no exploit, just nosy as fuck.")
            else:
                add_event('recon', f"Active recon refused: {result.get('error', 'unknown error')}")
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/known-devices':
            body = read_json_body(self)
            result = update_known_device(str(body.get('kind') or ''), str(body.get('id') or ''), body.get('label') if 'label' in body else None, body.get('trusted') if 'trusted' in body else None, body.get('watched') if 'watched' in body else None, bool(body.get('forget')))
            add_event('memory', f"Known device updated: {body.get('kind')} {body.get('id')}")
            return json_response(self, result)
        if path == '/api/wifi/target/action':
            body = read_json_body(self)
            result = wifi_target_action(str(body.get('ssid') or ''), str(body.get('action') or ''), body.get('label') if 'label' in body else None)
            add_event('wifi', result.get('message') or result.get('error') or 'Wi-Fi target action requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/wifi/psk/action':
            body = read_json_body(self)
            result = wifi_psk_action(str(body.get('ssid') or ''), str(body.get('action') or ''))
            add_event('wifi', result.get('message') or result.get('error') or 'Wi-Fi PSK action requested')
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/ai/chat':
            body = read_json_body(self)
            result = ai_chat_ask(str(body.get('prompt') or ''), str(body.get('model') or ''))
            add_event('ai', 'Dashboard AI answered.' if result.get('ok') else result.get('error', 'Dashboard AI failed.'))
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path.startswith('/api/services/') and path.endswith('/toggle'):
            name = path.split('/')[3]
            result = toggle_service(name)
            add_event('service', result.get('error') or VOICE.service_result(result.get('label', name), result.get('action', 'toggle'), result.get('active_text', 'unknown')))
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path.startswith('/api/externals/') and path.endswith('/control'):
            body = read_json_body(self)
            device_id = path.split('/')[3]
            action = str(body.get('action') or '')
            result = external_control(device_id, action)
            add_event('external', f"{device_id} control {action}: {'ok' if result.get('ok') else result.get('error', 'failed')}")
            return json_response(self, result, code=200 if result.get('ok') else 400)
        self.send_error(404)

    def log_message(self, format, *args):
        sys.stderr.write('[%s] %s\n' % (time.strftime('%H:%M:%S'), format % args))


def main():
    PLUGINS.load()
    metrics.start()
    add_event('boot', VOICE.starting())
    _trigger_status_refresh(force=True)
    # SPAC3GHOST_HOST / SPAC3GHOST_PORT override; otherwise bind to the Tailscale IP if up, else loopback.
    host = os.environ.get('SPAC3GHOST_HOST') or tailscale_ip() or '127.0.0.1'
    port = int(os.environ.get('SPAC3GHOST_PORT') or 8765)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f'Spac3-Gh0st listening at http://{host}:{port}', flush=True)
    def stop(*_):
        add_event('shutdown', 'Good night, little ghost.')
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
