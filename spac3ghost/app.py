from __future__ import annotations

import json
import mimetypes
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .collectors import active_recon, bluetooth_status, full_status, known_devices_status, known_wifi_passwords, lan_status, pwnagotchi_plugins, sensor_status, start_owned_lab_capture, tilt_status, update_known_device, weather_tile_url, wifi_status
from .config import load_config, save_config
from .controls import camera_status, external_control, external_status, launch_proton_gui, service_status, services_status, set_camera_feed, set_vision_enabled, tailscale_ip, toggle_service, toggle_vpn, vpn_status
from .personality import Spac3Voice, choose_mood, event_from_status, merged_faces
from .plugins import PluginManager
from .vision import SNAP_DIR, analyze_current_frame, jpeg_frame, vision_history

ROOT = Path('/home/pi/spac3-gh0st')
WEB = ROOT / 'web'
EVENTS = []
LAST_CHATTER = 0
LAST_PLUGIN_PANELS = []
VOICE = Spac3Voice()
PLUGINS = PluginManager()


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


def read_json_body(handler):
    length = int(handler.headers.get('Content-Length') or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode('utf-8'))


class Handler(BaseHTTPRequestHandler):
    server_version = 'Spac3-Gh0st/0.2'

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/api/status':
            status = full_status()
            status['vpn'] = vpn_status()
            status['vision'] = camera_status()
            status['vision_history'] = vision_history(8)
            status['controls'] = services_status()
            status['externals'] = external_status()
            status['tailscale_url'] = 'http://hack-safe.tailac984b.ts.net:8765' if tailscale_ip() else ''
            status['native_plugins'] = PLUGINS.describe()
            mood = choose_mood(status)
            status['mood'] = mood
            status['thought'] = event_from_status(status)['text']
            global LAST_CHATTER
            if time.time() - LAST_CHATTER >= 8:
                add_event('chatter', VOICE.chatter(status))
                LAST_CHATTER = time.time()
            status['events'] = list(reversed(EVENTS[-30:]))
            # Keep /api/status lightweight. Some plugin on_status callbacks perform
            # file/network/device work; don't run them every dashboard refresh.
            status['plugin_panels'] = list(LAST_PLUGIN_PANELS)
            status['config'] = load_config()
            status['faces'] = merged_faces()
            return json_response(self, status)
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
        if path == '/api/externals/status':
            return json_response(self, external_status())
        if path == '/api/plugins/pwnagotchi':
            return json_response(self, {'plugins': pwnagotchi_plugins()})
        if path == '/api/events':
            return json_response(self, {'events': list(reversed(EVENTS[-80:]))})
        if path == '/':
            path = '/index.html'
        file_path = (WEB / path.lstrip('/')).resolve()
        if not str(file_path).startswith(str(WEB.resolve())) or not file_path.exists() or file_path.is_dir():
            self.send_error(404)
            return
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
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
        if path == '/api/vpn/toggle':
            result = toggle_vpn()
            add_event('vpn', result.get('message') or result.get('error') or VOICE.vpn_result(result.get('action', 'toggle')))
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/vpn/open':
            result = launch_proton_gui()
            add_event('vpn', result.get('message') or result.get('error') or 'Proton GUI launch requested.')
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
        if path == '/api/camera/analyze':
            result = analyze_current_frame()
            labels = [d.get('label', 'object') for d in result.get('detections', [])[:4]]
            add_event('camera', VOICE.yolo_result(labels, result.get('error') or ''))
            return json_response(self, result, code=200 if result.get('ok') else 400)
        if path == '/api/pwnagotchi/capture':
            body = read_json_body(self)
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
    add_event('boot', VOICE.starting())
    host, port = tailscale_ip() or '127.0.0.1', 8765
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
