from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen
from urllib.error import URLError

from .config import load_config, save_config
from .vision import configured_feeds, last_analysis, vision_backend_status


def _run(cmd: List[str], timeout: int = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def _cmd_output(cmd: List[str], timeout: int = 4) -> str:
    try:
        cp = _run(cmd, timeout=timeout)
        if cp.returncode == 0:
            return cp.stdout.strip()
        return ''
    except Exception:
        return ''


def command_exists(name: str) -> bool:
    return bool(_cmd_output(['bash', '-lc', f'command -v {name}']))


def tailscale_ip() -> str:
    return (_cmd_output(['tailscale', 'ip', '-4'], timeout=3).splitlines() or [''])[0].strip()


def vpn_status() -> Dict[str, Any]:
    active_raw = _cmd_output(['nmcli', '-t', '-f', 'NAME,TYPE,STATE', 'connection', 'show', '--active'])
    all_raw = _cmd_output(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'])
    active = []
    profiles = []
    for line in active_raw.splitlines():
        parts = line.split(':')
        if len(parts) >= 3 and parts[1] in ('vpn', 'wireguard'):
            active.append({'name': parts[0], 'type': parts[1], 'state': parts[2]})
    for line in all_raw.splitlines():
        parts = line.split(':')
        if len(parts) >= 2 and (parts[1] in ('vpn', 'wireguard') or any(token in parts[0].lower() for token in ('proton', 'vpn', 'wireguard', 'wg'))):
            profiles.append({'name': parts[0], 'type': parts[1]})
    tools = [tool for tool in ('protonvpn-app', 'protonvpn', 'protonvpn-cli', 'wg', 'openvpn') if command_exists(tool)]
    preferred = load_config().get('vpn', {}).get('profile')
    selected = None
    if preferred:
        selected = next((p for p in profiles if p['name'] == preferred), None)
    if selected is None and profiles:
        selected = profiles[0]
    active_names = {item['name'] for item in active}
    configured = selected is not None
    proton_installed = any(tool in tools for tool in ('protonvpn-app', 'protonvpn', 'protonvpn-cli'))
    gui_running = bool(_cmd_output(['pgrep', '-f', 'protonvpn-app'], timeout=2))
    if active:
        button_label = 'Stop VPN'
    elif configured:
        button_label = 'Start VPN'
    elif gui_running:
        button_label = 'VPN Off'
    else:
        button_label = 'Open Proton'
    return {
        'configured': configured,
        'active': bool(active),
        'active_connections': active,
        'profiles': profiles,
        'selected_profile': selected,
        'tools': tools,
        'proton_installed': proton_installed,
        'gui_command': 'protonvpn-app' if command_exists('protonvpn-app') else '',
        'gui_running': gui_running,
        'message': (
            f"Ready to toggle {selected['name']}." if selected else
            'Proton GUI is installed. Use Open/Quick Connect in the app, then this button can stop active VPN connections.' if proton_installed else
            'No configured NetworkManager VPN/WireGuard profile found. Proton VPN is not installed/configured on this Pi.'
        ),
        'button_label': button_label,
    }


def launch_proton_gui() -> Dict[str, Any]:
    if not command_exists('protonvpn-app'):
        return {'ok': False, **vpn_status(), 'error': 'Proton VPN GUI command protonvpn-app is not installed.'}
    try:
        if not _cmd_output(['pgrep', '-f', 'protonvpn-app'], timeout=2):
            subprocess.Popen(['protonvpn-app'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.5)
        return {'ok': True, **vpn_status(), 'message': 'Opened Proton VPN GUI. Sign in and use the map/server picker there.'}
    except Exception as exc:
        return {'ok': False, **vpn_status(), 'error': str(exc)}


def toggle_vpn() -> Dict[str, Any]:
    status = vpn_status()
    active = status.get('active_connections') or []
    if active:
        results = []
        ok = True
        for item in active:
            cp = _run(['nmcli', 'connection', 'down', item['name']], timeout=20)
            results.append({'profile': item['name'], 'exit_code': cp.returncode, 'stdout': cp.stdout.strip(), 'stderr': cp.stderr.strip()})
            ok = ok and cp.returncode == 0
        return {'ok': ok, 'action': 'down', 'results': results, **vpn_status()}
    selected = status.get('selected_profile')
    if selected:
        cp = _run(['nmcli', 'connection', 'up', selected['name']], timeout=25)
        return {'ok': cp.returncode == 0, 'action': 'up', 'profile': selected['name'], 'stdout': cp.stdout.strip(), 'stderr': cp.stderr.strip(), **vpn_status()}
    launched = launch_proton_gui()
    return {'ok': launched.get('ok', False), 'action': 'open_gui', **launched, 'message': 'No saved VPN profile yet, so I opened Proton. Hit Quick Connect/map in Proton to start the tunnel.'}


_CAMERA_CACHE: Dict[str, Any] = {'ts': 0.0, 'data': None}
_TOOL_CACHE: Dict[str, bool] = {}


def cached_command_exists(name: str) -> bool:
    if name not in _TOOL_CACHE:
        _TOOL_CACHE[name] = command_exists(name)
    return _TOOL_CACHE[name]


def camera_status(force: bool = False) -> Dict[str, Any]:
    now = time.time()
    if not force and _CAMERA_CACHE.get('data') and now - float(_CAMERA_CACHE.get('ts', 0)) < 12:
        data = dict(_CAMERA_CACHE['data'])
        data['cached'] = True
        return data
    cfg = load_config()
    vision_cfg = cfg.get('vision', {}) if isinstance(cfg.get('vision'), dict) else {}
    if not vision_cfg.get('feeds'):
        vision_cfg.setdefault('selected_feed', 'local')
        vision_cfg['feeds'] = [
            {'id': 'local', 'label': 'Hack-Safe Cam', 'source': 'usb', 'device': vision_cfg.get('device', '/dev/video0')},
            {'id': 'bak3ry', 'label': 'theBAK3RY Cam', 'source': 'url', 'snapshot_url': vision_cfg.get('bak3ry_snapshot_url') or 'http://100.65.33.36:8091/snapshot.jpg'},
        ]
        cfg['vision'] = vision_cfg
        try:
            save_config(cfg)
        except Exception:
            pass
    videos = sorted(str(p) for p in Path('/dev').glob('video*'))
    remote_url = str(vision_cfg.get('stream_url') or vision_cfg.get('snapshot_url') or '').strip()
    feeds = configured_feeds(vision_cfg)
    for feed in feeds:
        source_f = str(feed.get('source') or '').lower()
        feed_url = str(feed.get('stream_url') or feed.get('snapshot_url') or '').strip()
        feed_device = str(feed.get('device') or vision_cfg.get('device') or '/dev/video0')
        feed['frame_url'] = f"/api/camera/frame?feed={feed.get('id')}"
        feed['available'] = bool(feed_url) if source_f in ('url', 'remote', 'esp32') else bool(feed_device in videos or '/dev/video0' in videos)
        feed['configured'] = bool(feed_url or source_f not in ('url', 'remote', 'esp32'))
    active_feed = str(vision_cfg.get('selected_feed') or vision_cfg.get('active_feed') or 'local')
    source = str(vision_cfg.get('source') or ('esp32' if remote_url else 'usb')).lower()
    usb_camera_available = bool(vision_cfg.get('device', '/dev/video0') in videos or '/dev/video0' in videos)
    remote_camera_available = bool(remote_url or any(f.get('configured') and str(f.get('source')) in ('url', 'remote', 'esp32') for f in feeds))
    # rpicam-hello --list-cameras can hang/heat the Pi on this setup. Only probe it
    # when there is no USB camera path visible; otherwise keep status lightweight.
    rpicam = _cmd_output(['rpicam-hello', '--list-cameras'], timeout=3) if (not usb_camera_available and not remote_camera_available and cached_command_exists('rpicam-hello')) else ''
    pi_camera_available = bool(rpicam and 'No cameras available' not in rpicam)
    camera_available = pi_camera_available or usb_camera_available or remote_camera_available
    tools = [tool for tool in ('rpicam-hello', 'fswebcam', 'v4l2-ctl') if cached_command_exists(tool)]
    backend = vision_backend_status()
    analysis = last_analysis()
    button_label = 'Disarm Vision' if vision_cfg.get('enabled') else 'Arm Vision'
    state_label = 'ARMED' if vision_cfg.get('enabled') else 'OFF'
    data = {
        'enabled': bool(vision_cfg.get('enabled')),
        'state_label': state_label,
        'button_label': button_label,
        'mode': vision_cfg.get('mode', 'manual'),
        'device': vision_cfg.get('device', '/dev/video0'),
        'source': source,
        'active_feed': active_feed,
        'feeds': feeds,
        'stream_url': remote_url,
        'camera_url': remote_url,
        'camera_available': camera_available,
        'remote_camera_available': remote_camera_available,
        'pi_camera_available': pi_camera_available,
        'usb_camera_available': usb_camera_available,
        'video_devices': videos,
        'tools': tools,
        'ai_backend': backend.get('backend') or vision_cfg.get('ai_backend', 'not_configured'),
        'ai_available': backend.get('available', False),
        'ai_model': backend.get('model', ''),
        'ai_error': backend.get('error', ''),
        'last_analysis': analysis,
        'frame_url': '/api/camera/frame',
        'cached': False,
        'message': (
            'Vision toggle is ON, but no camera is currently visible.' if vision_cfg.get('enabled') and not camera_available else
            'Vision toggle is ON. ESP32-S3/XIAO remote camera feed and local YOLO detection are ready.' if vision_cfg.get('enabled') and remote_camera_available and backend.get('available') else
            'Vision toggle is ON. USB camera feed and local YOLO detection are ready.' if vision_cfg.get('enabled') and backend.get('available') else
            'Vision toggle is ON. Camera is visible; AI backend still needs a local detector/model.' if vision_cfg.get('enabled') else
            'Vision is OFF. Camera watching remains opt-in.'
        ),
    }
    _CAMERA_CACHE.update({'ts': now, 'data': data})
    return data


def set_vision_enabled(enabled: bool) -> Dict[str, Any]:
    cfg = load_config()
    vision = cfg.setdefault('vision', {})
    vision['enabled'] = bool(enabled)
    vision.setdefault('mode', 'manual')
    vision.setdefault('device', '/dev/video0')
    vision.setdefault('ai_backend', 'yolo')
    vision.setdefault('analyze_interval_s', 4)
    vision.setdefault('width', 1280)
    vision.setdefault('height', 720)
    vision.setdefault('fps', 15)
    vision.setdefault('jpeg_quality', 90)
    vision.setdefault('selected_feed', 'local')
    vision.setdefault('feeds', [
        {'id': 'local', 'label': 'Hack-Safe Cam', 'source': 'usb', 'device': vision.get('device', '/dev/video0')},
        {'id': 'bak3ry', 'label': 'theBAK3RY Cam', 'source': 'url', 'snapshot_url': vision.get('bak3ry_snapshot_url', '')},
    ])
    save_config(cfg)
    status = camera_status(True)
    return {'ok': status.get('enabled') is bool(enabled), 'requested_enabled': bool(enabled), **status}


def set_camera_feed(feed_id: str) -> Dict[str, Any]:
    cfg = load_config()
    vision = cfg.setdefault('vision', {})
    feeds = configured_feeds(vision)
    ids = {str(feed.get('id')) for feed in feeds}
    selected = str(feed_id or '').strip().lower()
    if selected not in ids:
        return {'ok': False, 'error': f'Unknown camera feed: {feed_id}', 'feeds': feeds, 'active_feed': vision.get('selected_feed', 'local')}
    vision['selected_feed'] = selected
    save_config(cfg)
    status = camera_status(True)
    return {'ok': True, 'active_feed': selected, **status}


def external_devices_config() -> Dict[str, Any]:
    cfg = load_config()
    externals = cfg.setdefault('externals', {})
    devices = externals.setdefault('devices', {})
    changed = False
    if 'bak3ry' not in devices:
        changed = True
    devices.setdefault('bak3ry', {
        'id': 'bak3ry',
        'label': 'theBAK3RY',
        'kind': 'Raspberry Pi camera node',
        'host': '100.65.33.36',
        'user': 'cak3d',
        'camera_feed': 'bak3ry',
        'camera_url': 'http://100.65.33.36:8091/snapshot.jpg',
        'links': [
            {'label': 'Snapshot', 'url': 'http://100.65.33.36:8091/snapshot.jpg'},
            {'label': 'Heimdall', 'url': 'http://100.65.33.36:8080/'},
        ],
        'notes': ['Tailscale camera snapshot server', 'Password is not stored in Spac3-Gh0st.'],
    })
    if 'jeffeybot' not in devices:
        changed = True
    devices.setdefault('jeffeybot', {
        'id': 'jeffeybot',
        'label': 'Jeffeybot',
        'kind': 'SunFounder AI car / Raspberry Pi',
        'host': '192.168.18.42',
        'user': 'tinyz',
        'camera_feed': 'jeffeybot',
        'camera_url': 'http://192.168.18.42:5000/video_feed',
        'links': [
            {'label': 'Web', 'url': 'http://192.168.18.42/'},
            {'label': 'Car app', 'url': 'http://192.168.18.42:5000/'},
            {'label': 'Alt web', 'url': 'http://192.168.18.42:8000/'},
        ],
        'car_controls': {
            'forward': {'label': 'Forward', 'url': 'http://192.168.18.42:5000/run/?action=forward'},
            'left': {'label': 'Left', 'url': 'http://192.168.18.42:5000/run/?action=left'},
            'stop': {'label': 'Stop', 'url': 'http://192.168.18.42:5000/run/?action=stop'},
            'right': {'label': 'Right', 'url': 'http://192.168.18.42:5000/run/?action=right'},
            'backward': {'label': 'Backward', 'url': 'http://192.168.18.42:5000/run/?action=backward'},
        },
        'notes': ['Local LAN car controls only.', 'Password is not stored in Spac3-Gh0st.'],
    })
    # Persist non-secret device metadata only when bootstrapping defaults.
    if changed:
        save_config(cfg)
    return externals


def external_status() -> Dict[str, Any]:
    externals = external_devices_config()
    devices = []
    for key, dev in (externals.get('devices') or {}).items():
        item = dict(dev)
        item['id'] = str(item.get('id') or key)
        item['password_stored'] = False
        item['secret_note'] = 'credentials are not stored; use SSH manually if needed'
        devices.append(item)
    return {'devices': devices, 'count': len(devices)}


def external_control(device_id: str, action: str) -> Dict[str, Any]:
    externals = external_devices_config()
    dev = (externals.get('devices') or {}).get(device_id)
    if not dev:
        return {'ok': False, 'error': f'Unknown external device {device_id}'}
    controls = dev.get('car_controls') or {}
    ctrl = controls.get(action)
    if not ctrl:
        return {'ok': False, 'device': device_id, 'error': f'Unknown/unsupported action {action}'}
    url = str(ctrl.get('url') or '')
    if not url.startswith(('http://192.168.', 'http://100.', 'http://10.', 'http://172.')):
        return {'ok': False, 'device': device_id, 'action': action, 'error': 'Refusing non-private control URL'}
    try:
        req = Request(url, headers={'User-Agent': 'Spac3-Gh0st/0.2'})
        with urlopen(req, timeout=1.8) as resp:
            body = resp.read(500).decode(errors='replace')
        return {'ok': True, 'device': device_id, 'action': action, 'url': url, 'status': getattr(resp, 'status', 200), 'response': body[:250]}
    except Exception as exc:
        return {'ok': False, 'device': device_id, 'action': action, 'url': url, 'error': str(exc)}


SERVICE_MAP = {
    'vnc': {'unit': 'wayvnc.service', 'label': 'RealVNC/VNC', 'url': 'vnc://{tailscale}:5900'},
    'syncthing': {'unit': 'syncthing@pi.service', 'label': 'Syncthing', 'url': 'http://{tailscale}:8384'},
}


def _systemctl(unit: str, action: str) -> subprocess.CompletedProcess[str]:
    return _run(['sudo', '-n', 'systemctl', action, unit], timeout=25)


def service_status(name: str) -> Dict[str, Any]:
    info = SERVICE_MAP[name]
    unit = info['unit']
    active = _cmd_output(['systemctl', 'is-active', unit], timeout=3) or 'unknown'
    enabled = _cmd_output(['systemctl', 'is-enabled', unit], timeout=3) or 'unknown'
    ts_ip = tailscale_ip()
    return {
        'name': name,
        'label': info['label'],
        'unit': unit,
        'active': active == 'active',
        'active_text': active,
        'enabled_text': enabled,
        'url': info.get('url', '').format(tailscale=ts_ip) if ts_ip else '',
        'button_label': 'Stop' if active == 'active' else 'Start',
        'state_label': 'RUNNING' if active == 'active' else 'STOPPED',
    }


def services_status() -> Dict[str, Any]:
    return {name: service_status(name) for name in SERVICE_MAP}


def toggle_service(name: str) -> Dict[str, Any]:
    if name not in SERVICE_MAP:
        return {'ok': False, 'error': f'Unknown service {name}'}
    before = service_status(name)
    action = 'stop' if before['active'] else 'start'
    if action == 'start':
        _systemctl(before['unit'], 'reset-failed')
    cp = _systemctl(before['unit'], action)
    after = service_status(name)
    desired_active = action == 'start'
    verified = after['active'] is desired_active
    return {'ok': cp.returncode == 0 and verified, 'verified': verified, 'action': action, 'stdout': cp.stdout.strip(), 'stderr': cp.stderr.strip(), **after}
