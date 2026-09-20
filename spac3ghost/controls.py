from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen
from urllib.error import URLError

from .config import load_config, save_config
from .vision import configured_feeds, last_analysis, vision_backend_status


def _run(cmd: List[str], timeout: int = 8, env: Dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)


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


def _tailscale_json_status() -> Dict[str, Any]:
    try:
        cp = _run(['tailscale', 'status', '--json'], timeout=5)
        if cp.returncode == 0 and cp.stdout.strip():
            return json.loads(cp.stdout)
    except Exception:
        pass
    return {}


def tailscale_status() -> Dict[str, Any]:
    ip = tailscale_ip()
    active = (_cmd_output(['systemctl', 'is-active', 'tailscaled'], timeout=3) or 'unknown').strip()
    enabled = (_cmd_output(['systemctl', 'is-enabled', 'tailscaled'], timeout=3) or 'unknown').strip()
    version = (_cmd_output(['tailscale', 'version'], timeout=3).splitlines() or [''])[0].strip()
    j = _tailscale_json_status()
    self_node = j.get('Self') or {}
    backend = j.get('BackendState') or ''
    online = bool(ip) and active == 'active' and backend.lower() in ('running', 'starting', '')
    peers = []
    for _, peer in (j.get('Peer') or {}).items():
        name = str(peer.get('HostName') or peer.get('DNSName') or '').rstrip('.')
        if name:
            peers.append({'name': name, 'online': bool(peer.get('Online')), 'ip': (peer.get('TailscaleIPs') or [''])[0]})
    return {
        'ok': bool(ip), 'ip': ip, 'active': active == 'active', 'active_text': active,
        'enabled_text': enabled, 'backend_state': backend or 'unknown', 'online': online,
        'version': version, 'hostname': self_node.get('HostName') or '', 'dns_name': str(self_node.get('DNSName') or '').rstrip('.'),
        'peers_online': sum(1 for p in peers if p.get('online')), 'peers_total': len(peers), 'peers': peers[:12],
        'route_protection': 'accept-routes=false; tailscaled restart/up keeps SSH path recoverable',
        'button_label': 'Tailscale OK' if online else 'Recover Tailscale',
    }


def tailscale_up() -> Dict[str, Any]:
    cp = _run(['sudo', '-n', 'tailscale', 'up', '--ssh', '--accept-routes=false'], timeout=35)
    st = tailscale_status()
    return {'ok': cp.returncode == 0 and bool(st.get('ip')), 'action': 'up', 'stdout': cp.stdout.strip(), 'stderr': cp.stderr.strip(), **st}


def tailscale_restart() -> Dict[str, Any]:
    cp = _run(['sudo', '-n', 'systemctl', 'restart', 'tailscaled'], timeout=20)
    time.sleep(1.0)
    up = tailscale_up()
    return {'ok': cp.returncode == 0 and up.get('ok'), 'action': 'restart', 'restart_stdout': cp.stdout.strip(), 'restart_stderr': cp.stderr.strip(), **up}


def tailscale_protect() -> Dict[str, Any]:
    before = tailscale_status()
    up = tailscale_up()
    after = tailscale_status()
    return {'ok': bool(after.get('ip')), 'action': 'protect', 'before': before, 'after': after, 'message': 'Tailscale route protection applied: --accept-routes=false and SSH enabled.' if after.get('ip') else 'Tailscale protect attempted but no tailnet IP is visible.', **after}


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
        button_label = 'Open Hack-Safe VPN'
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
            'Hack-Safe VPN GUI is installed. Use Quick Connect/map in the app, then this button can stop active VPN connections.' if proton_installed else
            'No configured NetworkManager VPN/WireGuard profile found. Hack-Safe VPN is not installed/configured on this Pi.'
        ),
        'button_label': button_label,
    }


def launch_proton_gui() -> Dict[str, Any]:
    if not command_exists('protonvpn-app'):
        return {'ok': False, **vpn_status(), 'error': 'Hack-Safe VPN GUI command protonvpn-app is not installed.'}
    try:
        if not _cmd_output(['pgrep', '-f', 'protonvpn-app'], timeout=2):
            subprocess.Popen(['protonvpn-app'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.5)
        return {'ok': True, **vpn_status(), 'message': 'Opened Hack-Safe VPN GUI. Sign in and use the map/server picker there.'}
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
    return {'ok': launched.get('ok', False), 'action': 'open_gui', **launched, 'message': 'No saved VPN profile yet, so I opened Hack-Safe VPN. Hit Quick Connect/map in the VPN app to start the tunnel.'}


def _save_vpn_profile(name: str) -> None:
    cfg = load_config()
    vpn = cfg.setdefault('vpn', {})
    vpn['profile'] = name
    save_config(cfg)


def select_vpn_profile(name: str) -> Dict[str, Any]:
    name = str(name or '').strip()
    if not name:
        return {'ok': False, **vpn_status(), 'error': 'No VPN profile/country selected.'}
    status = vpn_status()
    profiles = status.get('profiles') or []
    exact = next((p for p in profiles if p.get('name') == name), None)
    if exact:
        _save_vpn_profile(exact['name'])
        return {'ok': True, 'action': 'select', 'profile': exact['name'], **vpn_status(), 'message': f'Selected VPN profile {exact["name"]}.'}
    lower = name.lower()
    alias = {
        'us-me': ['us', 'united states', 'america'], 'us-ny': ['us', 'united states', 'america'],
        'us-fl': ['us', 'united states', 'america'], 'us-tx': ['us', 'united states', 'america'],
        'us-ca': ['us', 'united states', 'america'], 'us-wa': ['us', 'united states', 'america'],
        'uk': ['uk', 'gb', 'united kingdom', 'britain'], 'nl': ['nl', 'netherlands'],
        'de': ['de', 'germany'], 'ch': ['ch', 'switzerland'], 'pl': ['pl', 'poland'],
        'se': ['se', 'sweden'], 'it': ['it', 'italy'], 'es': ['es', 'spain'], 'tr': ['tr', 'turkey'],
        'in': ['in', 'india'], 'sg': ['sg', 'singapore'], 'jp': ['jp', 'japan'],
        'au': ['au', 'australia'], 'br': ['br', 'brazil'], 'ar': ['ar', 'argentina'], 'za': ['za', 'south africa'],
        'fastest country': ['fastest', 'quick', 'proton']
    }
    terms = [lower] + alias.get(lower, [])
    found = None
    for p in profiles:
        pname = str(p.get('name') or '')
        plow = pname.lower()
        if any(t and t in plow for t in terms):
            found = p; break
    if found:
        _save_vpn_profile(found['name'])
        return {'ok': True, 'action': 'select', 'profile': found['name'], **vpn_status(), 'message': f'Mapped {name} to VPN profile {found["name"]}.'}
    if profiles:
        return {'ok': False, 'action': 'select', **status, 'error': f'No saved VPN profile matches {name}. Available profiles: ' + ', '.join(p.get('name','?') for p in profiles[:8])}
    return {'ok': False, 'action': 'select', **status, 'error': 'No NetworkManager VPN/WireGuard profiles are configured yet. Open Proton VPN once and save/import a profile first.'}


def connect_vpn_profile(name: str | None = None) -> Dict[str, Any]:
    if name:
        selected = select_vpn_profile(name)
        if not selected.get('ok'):
            status = vpn_status()
            if status.get('proton_installed') and not (status.get('profiles') or []):
                gui = launch_proton_gui()
                return {'ok': gui.get('ok', False), 'action': 'open_gui', **status, 'message': 'No saved NetworkManager VPN profiles exist yet, so I opened Proton VPN. Use Quick Connect/map in the Proton app once, or import/save a WireGuard/OpenVPN profile for one-click dashboard Start.', 'error': selected.get('error')}
            return selected
    status = vpn_status()
    active = status.get('active_connections') or []
    selected = status.get('selected_profile')
    if active:
        return {'ok': True, 'action': 'already_active', **status, 'message': 'VPN is already active: ' + ', '.join(i.get('name','?') for i in active)}
    if selected:
        ts_guard = tailscale_protect()
        cp = _run(['nmcli', 'connection', 'up', selected['name']], timeout=25)
        ts_after = tailscale_status()
        out = {'ok': cp.returncode == 0, 'action': 'up', 'profile': selected['name'], 'tailscale_guard': ts_guard, 'tailscale_after': ts_after, 'stdout': cp.stdout.strip(), 'stderr': cp.stderr.strip(), **vpn_status()}
        if not out['ok'] and not out.get('error'):
            out['error'] = cp.stderr.strip() or cp.stdout.strip() or 'nmcli connection up failed'
        return out
    return launch_proton_gui() | {'action': 'open_gui'}


_CAMERA_CACHE: Dict[str, Any] = {'ts': 0.0, 'data': None}
_TOOL_CACHE: Dict[str, bool] = {}


AI_CHAT_HISTORY = Path('/home/pi/spac3-gh0st/data/ai_chat_history.json')


def _http_json(url: str, payload: Dict[str, Any] | None = None, timeout: int = 20) -> Dict[str, Any]:
    data = None
    headers = {'Content-Type': 'application/json'}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
    req = Request(url, data=data, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def _read_chat_history() -> List[Dict[str, Any]]:
    try:
        if AI_CHAT_HISTORY.exists():
            data = json.loads(AI_CHAT_HISTORY.read_text())
            if isinstance(data, list):
                return data[-40:]
    except Exception:
        pass
    return []


def _write_chat_history(rows: List[Dict[str, Any]]) -> None:
    AI_CHAT_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    AI_CHAT_HISTORY.write_text(json.dumps(rows[-40:], indent=2))


def ai_chat_status() -> Dict[str, Any]:
    models: List[str] = []
    ollama_running = False
    error = ''
    try:
        data = _http_json('http://127.0.0.1:11434/api/tags', timeout=4)
        ollama_running = True
        models = [m.get('name', '') for m in data.get('models', []) if m.get('name')]
    except Exception as exc:
        error = str(exc)
    whisper_tools = {name: command_exists(name) for name in ('whisper', 'whisper-cli', 'whisper.cpp')}
    tts_tools = {name: command_exists(name) for name in ('espeak-ng', 'espeak', 'piper')}
    return {
        'ok': True,
        'ollama_running': ollama_running,
        'models': models,
        'selected_model': models[0] if models else '',
        'history': _read_chat_history()[-12:],
        'stt': {'available': any(whisper_tools.values()), 'tools': whisper_tools, 'note': 'Whisper STT can be added after storage check; keep model choice small on this Pi.'},
        'tts': {'available': any(tts_tools.values()), 'tools': tts_tools, 'note': 'TTS can use espeak-ng/piper if installed; browser voice can be added without large models.'},
        'storage_note': 'Avoid pulling large LLM/Whisper models while disk is tight; use installed Ollama models first.',
        'error': error,
    }


def ai_chat_ask(prompt: str, model: str = '') -> Dict[str, Any]:
    prompt = str(prompt or '').strip()
    model = str(model or '').strip()
    if not prompt:
        return {'ok': False, 'error': 'Ask something first.', 'chat': ai_chat_status()}
    st = ai_chat_status()
    if not st.get('ollama_running'):
        cp = _run(['sudo', '-n', 'systemctl', 'start', 'ollama.service'], timeout=45)
        time.sleep(1)
        st = ai_chat_status()
        if not st.get('ollama_running'):
            return {'ok': False, 'error': 'Ollama is not running and service start failed or is unavailable.', 'service_stdout': cp.stdout.strip(), 'service_stderr': cp.stderr.strip(), 'chat': st}
    if not model:
        model = st.get('selected_model') or ''
    if not model:
        return {'ok': False, 'error': 'No Ollama model is installed. Pull a small model first before using dashboard chat.', 'chat': st}
    context_bits = []
    try:
        from .collectors import sensor_status, wifi_status
        sens = sensor_status()
        wx = (sens.get('weather') or {}) if isinstance(sens, dict) else {}
        gps = (sens.get('gps') or {}) if isinstance(sens, dict) else {}
        wifi_now = (wifi_status(False).get('current') or {})
        if wx:
            context_bits.append(f"Weather now: {wx.get('summary','unknown')} {wx.get('tempF','?')}F, humidity {wx.get('humidity','?')}%, wind {wx.get('windMph','?')}mph, location {wx.get('location','unknown')}.")
        if gps:
            context_bits.append(f"GPS: fixed={gps.get('fixed')} sats={gps.get('satellitesUsed')}/{gps.get('satellitesVisible')}.")
        if wifi_now:
            context_bits.append(f"Wi-Fi: connected SSID {wifi_now.get('ssid','unknown')} signal {wifi_now.get('signal','?')}%.")
    except Exception:
        pass
    lower_prompt = prompt.lower()
    if 'weather' in lower_prompt and context_bits:
        answer = ' '.join(context_bits[:2]).strip() or 'Live weather context is unavailable right now.'
        rec = {'ts': int(time.time()), 'model': 'dashboard-live-context', 'user': prompt, 'assistant': answer}
        history = _read_chat_history(); history.append(rec); _write_chat_history(history)
        return {'ok': True, 'model': rec['model'], 'answer': answer, 'record': rec, 'chat': ai_chat_status()}
    system = 'You are Spac3-Gh0st, a concise local Pi dashboard assistant. Help with safe local system, lab, Wi-Fi, sensor, and dashboard questions. Use this live context when relevant: ' + ' '.join(context_bits) + ' Refuse illegal exploitation, credential theft, deauth against third-party networks, or harmful instructions.'
    history = _read_chat_history()
    messages = [{'role': 'system', 'content': system}]
    for row in history[-8:]:
        if row.get('user'):
            messages.append({'role': 'user', 'content': str(row.get('user'))[:1200]})
        if row.get('assistant'):
            messages.append({'role': 'assistant', 'content': str(row.get('assistant'))[:1600]})
    messages.append({'role': 'user', 'content': prompt[:3000]})
    try:
        data = _http_json('http://127.0.0.1:11434/api/chat', {'model': model, 'messages': messages, 'stream': False}, timeout=90)
        answer = (data.get('message') or {}).get('content') or data.get('response') or ''
    except Exception as exc:
        return {'ok': False, 'error': f'Ollama chat failed: {exc}', 'chat': st}
    rec = {'ts': int(time.time()), 'model': model, 'user': prompt, 'assistant': answer.strip()}
    history.append(rec); _write_chat_history(history)
    return {'ok': True, 'model': model, 'answer': answer.strip(), 'record': rec, 'chat': ai_chat_status()}


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
    private_prefixes = ('http://192.168.', 'http://100.', 'http://10.', 'http://172.')
    for feed in feeds:
        source_f = str(feed.get('source') or '').lower()
        feed_url = str(feed.get('stream_url') or feed.get('snapshot_url') or '').strip()
        feed_device = str(feed.get('device') or vision_cfg.get('device') or '/dev/video0')
        feed['frame_url'] = f"/api/camera/frame?feed={feed.get('id')}"
        feed['configured'] = bool(feed_url or source_f not in ('url', 'remote', 'esp32'))
        if source_f in ('url', 'remote', 'esp32'):
            feed['available'] = False
            feed['status_note'] = 'remote URL missing' if not feed_url else 'not checked'
            if feed_url.startswith(private_prefixes):
                try:
                    req = Request(feed_url, headers={'User-Agent': 'Spac3-Gh0st/0.2'})
                    with urlopen(req, timeout=1.2) as resp:
                        feed['http_status'] = getattr(resp, 'status', 200)
                        feed['content_type'] = resp.headers.get('content-type', '')
                        resp.read(1)
                    feed['available'] = 200 <= int(feed.get('http_status') or 0) < 500
                    feed['status_note'] = f"HTTP {feed.get('http_status')}"
                except Exception as exc:
                    feed['available'] = False
                    feed['status_note'] = str(exc)[:160]
            elif feed_url:
                feed['status_note'] = 'refusing non-private camera URL probe'
        else:
            feed['available'] = bool(feed_device in videos or '/dev/video0' in videos)
            feed['status_note'] = 'local video device visible' if feed['available'] else 'local video device missing'
    active_feed = str(vision_cfg.get('selected_feed') or vision_cfg.get('active_feed') or 'local')
    source = str(vision_cfg.get('source') or ('esp32' if remote_url else 'usb')).lower()
    usb_camera_available = bool(vision_cfg.get('device', '/dev/video0') in videos or '/dev/video0' in videos)
    remote_camera_available = any(f.get('available') and str(f.get('source')) in ('url', 'remote', 'esp32') for f in feeds) or bool(remote_url)
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
        {'id': 'bak3ry', 'label': 'theBAK3RY Cam', 'source': 'url', 'snapshot_url': vision.get('bak3ry_snapshot_url') or 'http://100.65.33.36:8091/snapshot.jpg'},
        {'id': 'jeffeybot', 'label': 'Jeffeybot Car Cam', 'source': 'url', 'snapshot_url': vision.get('jeffeybot_snapshot_url') or 'http://192.168.18.42:9000/mjpg'},
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
            {'label': 'Home Assistant', 'url': 'http://100.65.33.36:8123'},
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
        'camera_url': 'http://192.168.18.42:9000/mjpg',
        'links': [
            {'label': 'Web', 'url': 'http://192.168.18.42/'},
            {'label': 'Camera stream (/mjpg)', 'url': 'http://192.168.18.42:9000/mjpg'},
            {'label': 'Alt web (:8000 responds, routes unknown)', 'url': 'http://192.168.18.42:8000/'},
        ],
        'car_controls': None,
        'control_status': 'camera-only; movement controls disabled until approved',
        'notes': ['Local LAN car controls only.', 'Camera-only Vilib stream expected at :9000/mjpg; movement controls disabled until approved.', 'Password is not stored in Spac3-Gh0st.'],
    })
    # Persist non-secret device metadata only when bootstrapping defaults.
    if changed:
        save_config(cfg)
    return externals

_EXTERNAL_TELEMETRY_CACHE: Dict[str, Dict[str, Any]] = {}


def _pct_from_meminfo(text: str) -> Dict[str, Any]:
    vals: Dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].rstrip(':') in ('MemTotal', 'MemAvailable'):
            vals[parts[0].rstrip(':')] = int(parts[1])
    total = vals.get('MemTotal') or 0
    avail = vals.get('MemAvailable') or 0
    used = max(0, total - avail)
    pct = round((used / total) * 100, 1) if total else None
    return {'total_kb': total, 'available_kb': avail, 'used_kb': used, 'percent': pct}


def _external_telemetry(dev: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort live telemetry for other Pis; failures stay visible, not fatal."""
    host = str(dev.get('host') or '').strip()
    user = str(dev.get('user') or '').strip()
    cache_key = f"{user}@{host}"
    now = time.time()
    cached = _EXTERNAL_TELEMETRY_CACHE.get(cache_key)
    if cached and now - float(cached.get('ts', 0)) < 15:
        data = dict(cached.get('data') or {})
        data['cached'] = True
        return data
    data: Dict[str, Any] = {'ok': False, 'host': host, 'cached': False, 'ts': now}
    if not host:
        data['error'] = 'no host configured'
        return data
    ping = _run(['ping', '-c', '1', '-W', '1', host], timeout=2)
    data['ping_ok'] = ping.returncode == 0
    data['latency_ms'] = None
    if ping.stdout:
        import re
        m = re.search(r'time=([0-9.]+)\s*ms', ping.stdout)
        if m:
            data['latency_ms'] = float(m.group(1))
    camera_url = str(dev.get('camera_url') or '').strip()
    if camera_url.startswith(('http://192.168.', 'http://100.', 'http://10.', 'http://172.')):
        try:
            req = Request(camera_url, headers={'User-Agent': 'Spac3-Gh0st/0.2'})
            with urlopen(req, timeout=1.5) as resp:
                data['camera_http'] = getattr(resp, 'status', 200)
                data['camera_content_type'] = resp.headers.get('content-type', '')
        except Exception as exc:
            data['camera_error'] = str(exc)
    if user and data['ping_ok']:
        script = "python3 - <<'PY'\nimport json,os,subprocess\nmem=open('/proc/meminfo').read()\nload=open('/proc/loadavg').read().split()[:3]\ntemp=None\ntry: temp=int(open('/sys/class/thermal/thermal_zone0/temp').read().strip())/1000\nexcept Exception: pass\ndf=subprocess.getoutput('df -P / | tail -1')\nprint(json.dumps({'hostname':os.uname().nodename,'load':load,'cpu_temp_c':temp,'meminfo':mem,'disk_root':df}))\nPY"
        ssh = _run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=2', f'{user}@{host}', script], timeout=5)
        data['ssh_ok'] = ssh.returncode == 0
        if ssh.returncode == 0 and ssh.stdout.strip():
            try:
                remote = json.loads(ssh.stdout)
                data['system'] = {
                    'hostname': remote.get('hostname'),
                    'load': ' '.join(remote.get('load') or []),
                    'cpu_temp_c': remote.get('cpu_temp_c'),
                    'cpu_temp_f': round((remote['cpu_temp_c'] * 9 / 5) + 32, 1) if isinstance(remote.get('cpu_temp_c'), (int, float)) else None,
                    'memory': _pct_from_meminfo(remote.get('meminfo') or ''),
                    'disk_root': remote.get('disk_root') or '',
                }
            except Exception as exc:
                data['ssh_parse_error'] = str(exc)
        elif ssh.stderr:
            data['ssh_error'] = ssh.stderr.strip()[:220]
    data['ok'] = bool(data.get('system')) or bool(data.get('ping_ok'))
    _EXTERNAL_TELEMETRY_CACHE[cache_key] = {'ts': now, 'data': data}
    return data


def external_status() -> Dict[str, Any]:
    externals = external_devices_config()
    devices = []
    for key, dev in (externals.get('devices') or {}).items():
        item = dict(dev)
        item['id'] = str(item.get('id') or key)
        item['password_stored'] = False
        item['secret_note'] = 'credentials are not stored; live system stats use SSH only when key auth already works'
        item['telemetry'] = _external_telemetry(item)
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



SPICY_TOOL_DEFS = {
    'bettercap': {'label': 'Bettercap', 'commands': ['bettercap'], 'unit': 'bettercap.service', 'risk': 'high', 'mode': 'safe service disabled', 'description': 'Passive/owned-lab network console wrapper. Dashboard toggles do not run captures, MITM, spoofing, or deauth.'},
    'nexmon': {'label': 'Nexmon', 'commands': ['nexutil'], 'unit': '', 'risk': 'high', 'mode': 'capability only', 'description': 'Driver/firmware capability panel for monitor-mode Pi Wi-Fi. No firmware changes from dashboard.'},
    'security_onion': {'label': 'Security Onion ideas', 'commands': ['suricata', 'zeek'], 'unit': '', 'risk': 'medium', 'mode': 'status only', 'description': 'IDS-style summaries: Suricata/Zeek presence, alert/log links, top talkers later.'},
    'opennms': {'label': 'OpenNMS ideas', 'commands': ['opennms'], 'unit': 'opennms.service', 'risk': 'medium', 'mode': 'status only', 'description': 'NMS-style device/service checks, topology, uptime thresholds.'},
    'honeypi': {'label': 'HoneyPi', 'commands': ['cowrie', 'opencanaryd', 'opencanary'], 'unit': '', 'risk': 'medium', 'mode': 'isolated/off by default', 'description': 'Cowrie/OpenCanary-inspired honeypot status/event feed. Separate approval before exposing listeners.'},
    'p4wnaloha': {'label': 'P4wnP1 A.L.O.H.A posture', 'commands': ['P4wnP1_cli', 'p4wnp1'], 'unit': '', 'risk': 'high', 'mode': 'defensive USB posture', 'description': 'USB gadget/interface posture viewer. Payload launching stays disabled.'},
    'aircrack': {'label': 'Kali Wi-Fi toolbelt', 'commands': ['aircrack-ng', 'airodump-ng', 'aireplay-ng', 'hcxdumptool', 'hcxpcapngtool'], 'unit': '', 'risk': 'high', 'mode': 'installed status only', 'description': 'Tool presence and adapter readiness only. No cracking/deauth/capture from safe toggles.'},
    'pwnagotchi': {'label': 'Pwnagotchi posture', 'commands': ['pwnagotchi'], 'unit': 'pwnagotchi.service', 'risk': 'high', 'mode': 'manual/passive readiness', 'description': 'Pwnagotchi-style service/readiness panel. Safe enable stages manual/passive mode only; deauth/capture needs owned-lab adapter approval.'},
}


def _unit_state(unit: str) -> Dict[str, Any]:
    if not unit:
        return {'unit': '', 'active': False, 'enabled': False, 'active_text': 'n/a', 'enabled_text': 'n/a'}
    active = _cmd_output(['systemctl', 'is-active', unit], timeout=2) or 'unknown'
    enabled = _cmd_output(['systemctl', 'is-enabled', unit], timeout=2) or 'unknown'
    return {'unit': unit, 'active': active == 'active', 'enabled': enabled == 'enabled', 'active_text': active, 'enabled_text': enabled}



def _unit_exists(unit: str) -> bool:
    if not unit:
        return False
    cp = _run(['systemctl', 'cat', unit], timeout=4)
    return cp.returncode == 0


LAB_SOFTWARE_DEFS = {
    'ollama': {
        'label': 'Ollama Local LLM',
        'source': 'https://ollama.com/',
        'home': 'Lab Operations + Local AI',
        'paths': ['/usr/local/bin/ollama', '/home/pi/.ollama'],
        'commands': ['ollama'],
        'unit': 'ollama.service',
        'unit_scope': 'system',
        'url': 'http://127.0.0.1:11434',
        'summary': 'Local model server for Spac3-Gh0st/Open WebUI experiments. Runs on loopback by default; start/stop is service-backed.',
        'needed': ['ollama.service installed', 'at least one pulled model', 'Open WebUI or API client if you want a browser chat UI'],
        'blocked_actions': ['internet exposure without auth/proxy', 'auto-pulling large models on dashboard refresh'],
        'safe_mode': 'service toggle/readiness only; model pulls stay manual/explicit',
    },
    'openwebui': {
        'label': 'Open WebUI',
        'source': 'https://github.com/open-webui/open-webui',
        'home': 'Lab Operations + Local AI',
        'paths': ['/home/pi/apps/open-webui', '/home/pi/open-webui', '/opt/open-webui'],
        'commands': ['open-webui'],
        'unit': 'open-webui.service',
        'unit_scope': 'system',
        'url': 'http://100.75.120.80:3002',
        'summary': 'Browser UI for Ollama/local models. Not assumed present unless path/unit/command is actually detected.',
        'needed': ['Open WebUI install or container', 'non-conflicting port; 3000 is already used here', 'Ollama reachable at 127.0.0.1:11434'],
        'blocked_actions': ['silent install', 'port 3000 collision with Hermes Workspace', 'public exposure without login/auth'],
        'safe_mode': 'readiness/open card only until installed with an explicit port choice',
    },

    'uptimekuma': {
        'label': 'Uptime Kuma',
        'source': 'https://github.com/louislam/uptime-kuma',
        'home': 'Operations + Monitoring',
        'paths': ['/home/pi/apps/uptime-kuma', '/home/pi/uptime-kuma'],
        'commands': ['docker'],
        'unit': 'uptime-kuma.service',
        'unit_scope': 'user',
        'url': 'http://100.75.120.80:3001',
        'summary': 'Self-hosted uptime/status monitor for Pi services and lab endpoints.',
        'needed': ['cak3d-uptime-kuma Docker container or uptime-kuma.service', 'port 3001 reachable on Tailnet'],
        'blocked_actions': ['public unauthenticated exposure', 'auto-creating monitors without review'],
        'safe_mode': 'open/status card; service managed by existing user unit/container',
    },
    'docker': {
        'label': 'Docker Engine',
        'source': 'https://docs.docker.com/',
        'home': 'Operations + Containers',
        'paths': ['/var/run/docker.sock', '/usr/bin/docker'],
        'commands': ['docker'],
        'unit': 'docker.service',
        'unit_scope': 'system',
        'url': '',
        'summary': 'Container runtime behind Project N.O.M.A.D, Uptime Kuma, and other local stacks.',
        'needed': ['docker.service active', 'docker ps available'],
        'blocked_actions': ['blind prune/delete', 'pull/run arbitrary public containers'],
        'safe_mode': 'status/readiness only; destructive container actions stay out of this generic card',
    },
    'portainer': {
        'label': 'Portainer',
        'source': 'https://www.portainer.io/',
        'home': 'Operations + Containers',
        'paths': [],
        'commands': ['docker'],
        'unit': '',
        'unit_scope': 'docker',
        'url': 'https://100.75.120.80:9443',
        'summary': 'Browser UI for Docker containers, images, volumes, and stacks on this Pi.',
        'needed': ['portainer Docker container', 'docker.sock mounted read/write', 'port 9443 reachable on Tailnet'],
        'blocked_actions': ['blind prune/delete of containers, images, or volumes'],
        'safe_mode': 'open Docker UI; destructive container changes require care',
    },
    'hermesworkspace': {
        'label': 'Hermes Workspace',
        'source': 'https://hermes-agent.nousresearch.com/docs',
        'home': 'Operations + Hermes',
        'paths': ['/home/pi/.hermes'],
        'commands': ['node'],
        'unit': 'hermes-workspace.service',
        'unit_scope': 'user',
        'url': 'http://100.75.120.80:3000',
        'summary': 'Hermes browser workspace already occupying port 3000; Open WebUI must avoid that port.',
        'needed': ['hermes-workspace.service or node listener on 3000'],
        'blocked_actions': ['port collision with Open WebUI', 'killing active Hermes session from generic launcher'],
        'safe_mode': 'open/status card only',
    },
    'godseye': {
        'label': "God's Eye View",
        'source': 'https://github.com/bilawalsidhu/gods-eye-view',
        'home': 'Vision + OSINT Globe',
        'paths': ['/home/pi/apps/gods-eye-view', '/home/pi/spac3-gh0st/web/godseye-app'],
        'commands': ['node', 'npm'],
        'unit': 'godseye-live.service',
        'unit_scope': 'user',
        'url': 'http://100.75.120.80:8765/godseye-live/',
        'summary': 'Live OSINT globe proxied through Spac3-Gh0st. Heavy Vite dev server is the current CPU hotspot.',
        'needed': ['static fallback exists', 'live Vite service only when needed'],
        'blocked_actions': ['leaving dev server hot when not using the globe', 'unbounded API polling'],
        'safe_mode': 'open/status card; static fallback preferred for low CPU',
    },
    'jellyfin': {
        'label': 'Jellyfin',
        'source': 'https://jellyfin.org/',
        'home': 'Media + Services',
        'paths': ['/etc/jellyfin', '/var/lib/jellyfin'],
        'commands': [],
        'unit': 'jellyfin.service',
        'unit_scope': 'system',
        'url': 'http://100.75.120.80:8096',
        'summary': 'Local media server already integrated as a service endpoint.',
        'needed': ['jellyfin.service active', 'port 8096 reachable'],
        'blocked_actions': ['media library deletion from generic launcher'],
        'safe_mode': 'open/status card only',
    },
    'syncthing': {
        'label': 'Syncthing',
        'source': 'https://syncthing.net/',
        'home': 'Sync + Services',
        'paths': ['/home/pi/.local/state/syncthing', '/home/pi/.config/syncthing'],
        'commands': ['syncthing'],
        'unit': 'syncthing@pi.service',
        'unit_scope': 'system',
        'url': 'http://100.75.120.80:8384',
        'summary': 'Local file sync UI and service already exposed on Tailnet.',
        'needed': ['syncthing service active', 'port 8384 reachable'],
        'blocked_actions': ['blind folder/share deletion'],
        'safe_mode': 'open/status card only',
    },
    'bjorn': {
        'label': 'Bjorn CyberViking',
        'source': 'https://github.com/infinition/Bjorn',
        'home': 'Lab Operations + RF Audit',
        'paths': ['/home/pi/apps/Bjorn', '/home/pi/Bjorn'],
        'commands': ['nmap', 'python3'],
        'unit': 'bjorn-safe-manual.service',
        'unit_scope': 'user',
        'summary': 'Raspberry Pi/e-paper cyber-pet style network scanning and vulnerability-assessment suite. Spac3-Gh0st exposes readiness and gated launch prep only.',
        'needed': ['Bjorn repo installed in /home/pi/apps/Bjorn', 'Python dependencies in a venv', 'authorized home-lab target scope', 'optional 2.13-inch e-paper HAT'],
        'blocked_actions': ['automatic scans', 'data exfiltration', 'third-party targets', 'credential collection'],
        'safe_mode': 'disabled by default; check/stage only until CAK3D selects an owned-lab target',
    },
    'projectnomad': {
        'label': 'Project N.O.M.A.D',
        'source': 'https://github.com/Crosstalk-Solutions/project-nomad',
        'home': 'Lab Operations + Field Kit',
        'paths': ['/home/pi/apps/project-nomad', '/home/pi/project-nomad'],
        'commands': ['git', 'docker'],
        'unit': 'project-nomad.service',
        'unit_scope': 'user',
        'url': 'http://100.75.120.80:8080',
        'summary': 'Offline survival/field computer stack: local knowledge, tools, maps/docs, and resilient-use ideas for opening when needed.',
        'needed': ['Project Nomad repo/content installed', 'storage/media prepared', 'local web/docs launcher if chosen'],
        'blocked_actions': ['internet-dependent claims while offline', 'secret sync', 'unsafe system reconfiguration'],
        'safe_mode': 'launcher/readiness only; no install or system changes from generic toggle',
    },
    'securitylab': {
        'label': 'Raspberry Pi Security Lab',
        'source': 'https://github.com/ExploitGd/raspberry-pi-security-lab',
        'home': 'Defensive Ops + Lab Operations',
        'paths': ['/home/pi/apps/raspberry-pi-security-lab', '/home/pi/raspberry-pi-security-lab'],
        'commands': ['git', 'ufw', 'fail2ban-client', 'suricata', 'python3'],
        'unit': '',
        'unit_scope': 'system',
        'url': 'http://100.75.120.80:3000',
        'summary': 'Blue-team Pi 5 lab: hardening, UFW/fail2ban, Suricata IDS, Cowrie honeypot, Promtail/Loki/Grafana-style log visibility.',
        'needed': ['clone repo under /home/pi/apps/raspberry-pi-security-lab', 'review scripts before running', 'pick monitored interface', 'decide if SSH/firewall hardening is safe for this Tailscale Pi'],
        'blocked_actions': ['blind firewall/SSH lockout changes', 'internet-exposed honeypot without isolation', 'heavy Grafana/Loki install without storage check', 'running repo scripts without review'],
        'safe_mode': 'readiness/install staging only; script execution stays manual/explicit because hardening can lock you out',
    },
    'homeassistant': {
        'label': 'Home Assistant @ theBAK3RY',
        'source': 'http://100.65.33.36:8123',
        'home': 'External Dashboards',
        'paths': [],
        'commands': [],
        'unit': '', 'unit_scope': 'external',
        'url': 'http://100.65.33.36:8123',
        'summary': 'Home Assistant hosted on theBAK3RY. Dashboard button opens the verified Tailnet URL.',
        'needed': ['theBAK3RY reachable over Tailscale', 'Home Assistant login in browser'],
        'blocked_actions': ['credential reset from Spac3-Gh0st', 'blind automations'],
        'safe_mode': 'external open link only',
    },
    'heimdall': {
        'label': 'Heimdall @ theBAK3RY',
        'source': 'http://100.65.33.36:8080',
        'home': 'External Dashboards',
        'paths': [],
        'commands': [],
        'unit': '', 'unit_scope': 'external',
        'url': 'http://100.65.33.36:8080',
        'summary': 'Heimdall dashboard hosted on theBAK3RY. Dashboard button opens the verified Tailnet URL.',
        'needed': ['theBAK3RY reachable over Tailscale'],
        'blocked_actions': ['credential reset from Spac3-Gh0st'],
        'safe_mode': 'external open link only',
    },
    'ruview': {
        'label': 'RuView WiFi Sensing',
        'source': 'https://github.com/ruvnet/RuView',
        'home': 'Signals + RF/CSI + Home Assistant',
        'paths': ['/home/pi/apps/RuView', '/home/pi/spac3-gh0st/web/ruview'],
        'commands': ['git', 'python3'],
        'unit': '',
        'unit_scope': 'user',
        'url': 'http://100.75.120.80:8765/ruview/index.html',
        'summary': 'RuView WiFi CSI / presence sensing reference and static UI, staged locally for ESP32-S3/CSI hardware experiments.',
        'needed': ['ESP32-S3/C6 CSI node hardware', 'RuView repo under /home/pi/apps/RuView', 'static UI mirrored under Spac3-Gh0st web/ruview', 'Home Assistant/MQTT integration later'],
        'blocked_actions': ['privacy-invasive sensing without consent', 'claims of real room/vital sensing before hardware CSI validation', 'flashing firmware without explicit approval'],
        'safe_mode': 'open static UI/reference; live sensing requires explicit hardware setup and consent',
    },
    'sdrsuite': {
        'label': 'SDR / rtl_433 / SoapySDR',
        'source': 'https://github.com/AlexandreRouma/SDRPlusPlus',
        'home': 'Signals + RF/SDR',
        'paths': [],
        'commands': ['rtl_test', 'rtl_sdr', 'rtl_433', 'SoapySDRUtil'],
        'unit': '',
        'unit_scope': 'system',
        'url': '',
        'summary': 'SDR readiness for RTL-SDR/433MHz receive workflows. GUI SDR++ is source-tracked; installed Pi tools are rtl-sdr/rtl_433/Soapy modules.',
        'needed': ['RTL-SDR/HackRF/Airspy receiver plugged in', 'antenna matched to band', 'owned/legal receive-only use'],
        'blocked_actions': ['transmit/jam', 'privacy-invasive decoding', 'claim SDR++ GUI installed when only CLI receivers are present'],
        'safe_mode': 'receive/readiness only; dashboard never transmits RF',
    },
    'cyberradar': {
        'label': 'CyberRadar Reference',
        'source': 'https://github.com/ahmedhamdy3hh/cyberradar',
        'home': 'Defensive Ops + Situation Radar',
        'paths': ['/home/pi/apps/cyberradar'],
        'commands': ['git', 'python3'],
        'unit': '',
        'unit_scope': 'user',
        'url': '',
        'summary': 'Network intelligence/situational-awareness reference repo. Cloned as code reference only until reviewed.',
        'needed': ['shallow clone under /home/pi/apps/cyberradar', 'review dependencies/scripts', 'map safe parts into Spac3-Gh0st cards'],
        'blocked_actions': ['auto-running scanners', 'unknown setup scripts', 'internet-wide scanning'],
        'safe_mode': 'clone/check/open folder only; no auto-run',
    },
    'flockcamera': {
        'label': 'Flock Camera Pi Reference',
        'source': 'https://github.com/search?q=flock+camera+raspberry+pi&type=repositories',
        'home': 'Externals + Vision',
        'paths': ['/home/pi/apps/flock-camera-reference'],
        'commands': ['git', 'python3'],
        'unit': '',
        'unit_scope': 'user',
        'url': '',
        'summary': 'Placeholder for a Pi-compatible Flock camera repo; search did not identify a clear canonical Raspberry Pi repo yet.',
        'needed': ['select exact repo', 'verify Pi/ARM compatibility', 'review camera/privacy behavior'],
        'blocked_actions': ['installing random camera surveillance repo without selecting/reviewing it', 'unapproved public streaming'],
        'safe_mode': 'selection/check card only until exact repo is chosen',
    },
    'payloadsallthethings': {
        'label': 'PayloadsAllTheThings',
        'source': 'https://github.com/swisskyrepo/PayloadsAllTheThings',
        'home': 'Reference Library',
        'paths': ['/home/pi/apps/security-references/PayloadsAllTheThings'],
        'commands': ['git'],
        'unit': '', 'unit_scope': 'user', 'url': '',
        'summary': 'Curated security testing notes/reference content. Stored locally as read-only reference; not executable payload launcher.',
        'needed': ['shallow clone if storage allows', 'use as docs/reference only'],
        'blocked_actions': ['running payloads automatically', 'credential theft', 'third-party exploitation'],
        'safe_mode': 'reference/docs only',
    },
    'hacktricks': {
        'label': 'HackTricks',
        'source': 'https://github.com/HackTricks-wiki/hacktricks',
        'home': 'Reference Library',
        'paths': ['/home/pi/apps/security-references/hacktricks'],
        'commands': ['git'],
        'unit': '', 'unit_scope': 'user', 'url': '',
        'summary': 'HackTricks security knowledge base as local reference docs where storage permits.',
        'needed': ['shallow clone if selected', 'docs-only use'],
        'blocked_actions': ['auto-running exploit snippets', 'third-party exploitation'],
        'safe_mode': 'reference/docs only',
    },
    'seclists': {
        'label': 'SecLists',
        'source': 'https://github.com/danielmiessler/SecLists',
        'home': 'Reference Library',
        'paths': ['/home/pi/apps/security-references/SecLists'],
        'commands': ['git'],
        'unit': '', 'unit_scope': 'user', 'url': '',
        'summary': 'Security test wordlists. Large repo; clone is explicit and remains reference inventory, not an attack runner.',
        'needed': ['confirm storage', 'owned-lab testing only'],
        'blocked_actions': ['credential attacks', 'spraying/bruteforce against third parties'],
        'safe_mode': 'reference/docs only; no automatic use in scans',
    },
    'awesomehacking': {
        'label': 'Awesome Hacking',
        'source': 'https://github.com/Hack-with-Github/Awesome-Hacking',
        'home': 'Reference Library',
        'paths': ['/home/pi/apps/security-references/Awesome-Hacking'],
        'commands': ['git'],
        'unit': '', 'unit_scope': 'user', 'url': '',
        'summary': 'Curated links to security tools and references; local clone is a launch/reference index only.',
        'needed': ['shallow clone', 'review links before use'],
        'blocked_actions': ['blind install/run of linked tools'],
        'safe_mode': 'reference/docs only',
    },
    'awesomebugbounty': {
        'label': 'Awesome Bug Bounty',
        'source': 'https://github.com/djadmin/awesome-bug-bounty',
        'home': 'Reference Library',
        'paths': ['/home/pi/apps/security-references/awesome-bug-bounty'],
        'commands': ['git'],
        'unit': '', 'unit_scope': 'user', 'url': '',
        'summary': 'Bug bounty programs/writeups reference index. For authorized programs only.',
        'needed': ['shallow clone', 'authorized program scope'],
        'blocked_actions': ['testing out-of-scope targets', 'auto-scanning programs'],
        'safe_mode': 'reference/docs only',
    },
    'hackingtool': {
        'label': 'Z4nzu HackingTool',
        'source': 'https://github.com/Z4nzu/hackingtool',
        'home': 'Reference Library',
        'paths': ['/home/pi/apps/security-references/hackingtool'],
        'commands': ['git', 'python3'],
        'unit': '', 'unit_scope': 'user', 'url': '',
        'summary': 'Large curated security-tool launcher/reference repo. Staged here as docs/code reference only; Spac3-Gh0st will not run its installer or offensive modules from the generic dashboard.',
        'needed': ['shallow clone under /home/pi/apps/security-references/hackingtool', 'manual review of categories/tools before use', 'owned/authorized lab scope for any external testing'],
        'blocked_actions': ['auto-running setup.py or installer scripts', 'credential attacks', 'third-party exploitation', 'deauth/MITM/phishing/payload execution from dashboard controls'],
        'safe_mode': 'reference/staged inventory only; Check/Open report the local path, no automatic tool execution',
    },
    'conflictly': {
        'label': 'Conflictly',
        'source': 'https://conflictly.app',
        'home': 'Reference Library',
        'paths': [],
        'commands': [],
        'unit': '', 'unit_scope': 'external', 'url': 'https://conflictly.app',
        'summary': 'External Conflictly web app link, staged as an OSINT/reference launcher only. Spac3-Gh0st opens the site; it does not scrape, attack, or automate third-party targets.',
        'needed': ['internet/browser access', 'user-selected lawful research scope', 'manual review before using any external data'],
        'blocked_actions': ['automated scraping from dashboard', 'third-party targeting without authorization', 'credential collection or harassment workflows'],
        'safe_mode': 'external open link only; manual lawful research scope required',
    },
    'osirisosint': {
        'label': 'OSIRIS AI Live',
        'source': 'https://www.osirisai.live/?layers=maritime,cctv,cctv_previews,live_news,earthquakes,global_incidents,day_night,cables,sdk_sea,sdk_air,sdk_naval',
        'home': 'Vision + OSINT Globe',
        'paths': [],
        'commands': [],
        'unit': '', 'unit_scope': 'external',
        'url': 'https://www.osirisai.live/?layers=maritime,cctv,cctv_previews,live_news,earthquakes,global_incidents,day_night,cables,sdk_sea,sdk_air,sdk_naval',
        'summary': 'External OSIRIS AI Live globe/OSINT map with maritime, CCTV previews, live news, earthquakes, incidents, day/night, cables, sea/air/naval layers preselected.',
        'needed': ['internet/browser access', 'manual lawful research scope', 'do not treat third-party feeds as household/device evidence without verification'],
        'blocked_actions': ['automated scraping from dashboard', 'tracking or targeting people', 'credential collection', 'third-party surveillance or harassment'],
        'safe_mode': 'external open link only; human-reviewed lawful OSINT use',
    },
    'leolabsleo': {
        'label': 'LeoLabs LEO Visualization',
        'source': 'https://platform.leolabs.space/visualizations/leo',
        'home': 'Space / LEO Tracking',
        'paths': [],
        'commands': [],
        'unit': '', 'unit_scope': 'external',
        'url': 'https://platform.leolabs.space/visualizations/leo',
        'summary': 'External LeoLabs low-earth-orbit satellite visualization link for space situational awareness/reference.',
        'needed': ['internet/browser access', 'LeoLabs platform availability/login if required by the site'],
        'blocked_actions': ['automated scraping from dashboard', 'claiming live satellite tasking/control', 'third-party data misuse'],
        'safe_mode': 'external open link only; visualization/reference use',
    },
}


def _lab_software_config() -> Dict[str, Any]:
    cfg = load_config()
    software = cfg.setdefault('lab_software', {})
    for sid in LAB_SOFTWARE_DEFS:
        software.setdefault(sid, {'enabled': False, 'last_message': ''})
    return cfg


def lab_software_status() -> Dict[str, Any]:
    cfg = _lab_software_config()
    save_config(cfg)
    states = cfg.get('lab_software', {})
    modules = []
    for sid, meta in LAB_SOFTWARE_DEFS.items():
        paths = [Path(p) for p in meta.get('paths', [])]
        existing = [str(p) for p in paths if p.exists()]
        commands = meta.get('commands') or []
        found = [c for c in commands if command_exists(c)]
        unit_name = str(meta.get('unit') or '')
        unit_scope = str(meta.get('unit_scope') or 'system')
        if unit_name and unit_scope == 'user':
            active = _cmd_output(['systemctl', '--user', 'is-active', unit_name], timeout=2) or 'unknown'
            enabled_txt = _cmd_output(['systemctl', '--user', 'is-enabled', unit_name], timeout=2) or 'unknown'
            unit = {'unit': unit_name, 'scope': 'user', 'active': active == 'active', 'enabled': enabled_txt == 'enabled', 'active_text': active, 'enabled_text': enabled_txt}
            unit_exists = _run(['systemctl', '--user', 'cat', unit_name], timeout=4).returncode == 0
        else:
            unit = _unit_state(unit_name) if unit_name else {'unit': '', 'active': False, 'enabled': False, 'active_text': 'n/a', 'enabled_text': 'n/a'}
            unit_exists = _unit_exists(unit_name) if unit_name else False
        if sid == 'uptimekuma':
            container = _cmd_output(['bash', '-lc', "docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -E '^cak3d-uptime-kuma ' || true"], timeout=4)
            if container:
                unit['active'] = True
                unit['active_text'] = 'container running'
                unit_exists = True
        if sid == 'openwebui':
            container = _cmd_output(['bash', '-lc', "docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -E '^open-webui ' || true"], timeout=4)
            listening = _cmd_output(['bash', '-lc', "ss -ltn 2>/dev/null | grep -q ':3002 ' && echo up || true"], timeout=3)
            if container or listening:
                unit['active'] = True
                unit['active_text'] = 'container running' if container else 'port 3002 listening'
                unit_exists = True
            elif _cmd_output(['bash', '-lc', "docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx open-webui && echo exists || true"], timeout=4):
                unit_exists = True
                existing.append('docker:open-webui')
        if sid == 'portainer':
            container = _cmd_output(['bash', '-lc', "docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -E '^portainer ' || true"], timeout=4)
            listening = _cmd_output(['bash', '-lc', "ss -ltn 2>/dev/null | grep -q ':9443 ' && echo up || true"], timeout=3)
            exists = _cmd_output(['bash', '-lc', "docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx portainer && echo exists || true"], timeout=4)
            if container or listening:
                unit['active'] = True
                unit['active_text'] = 'container running' if container else 'port 9443 listening'
                unit_exists = True
            elif exists:
                unit_exists = True
                existing.append('docker:portainer')
        if sid == 'hermesworkspace':
            if _cmd_output(['bash', '-lc', "ss -ltn 2>/dev/null | grep -q ':3000 ' && echo up || true"], timeout=3):
                unit['active'] = True
                unit['active_text'] = 'port 3000 listening'
                unit_exists = True
        if sid == 'projectnomad':
            containers = _cmd_output(['bash', '-lc', "docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -E '^nomad_(admin|redis|mysql) ' || true"], timeout=4)
            listening = _cmd_output(['bash', '-lc', "ss -ltn 2>/dev/null | grep -q ':8080 ' && echo up || true"], timeout=3)
            if containers or listening:
                unit['active'] = True
                unit['active_text'] = 'containers running' if containers else 'port 8080 listening'
                unit_exists = True
            else:
                unit['active'] = False
                unit['active_text'] = 'stopped'
        if sid in ('homeassistant', 'heimdall', 'conflictly', 'osirisosint', 'leolabsleo'):
            unit['active'] = True
            unit['active_text'] = 'external web URL staged'
            unit_exists = True
        if sid == 'ruview' and Path('/home/pi/spac3-gh0st/web/ruview/index.html').exists():
            unit['active'] = True
            unit['active_text'] = 'static UI mirrored under Spac3-Gh0st'
            unit_exists = True
        installed = bool(existing) or unit_exists or bool(found)
        enabled = bool(states.get(sid, {}).get('enabled', False))
        missing = [c for c in commands if c not in found]
        if sid == 'ollama':
            readiness = 'installed/running local model API' if installed and unit.get('active') else ('installed but stopped; use Open / Prep to start the service' if installed else 'not installed yet')
        elif sid == 'openwebui':
            readiness = 'installed/openable browser UI detected' if installed and unit.get('active') else ('installed but stopped/not listening' if installed else 'not installed yet; needs explicit install/port choice because 3000 is already in use')
        elif sid == 'bjorn':
            readiness = 'installed; choose an owned-lab target before launch' if installed else 'not installed yet; safe card can track setup requirements'
        elif sid == 'projectnomad':
            readiness = 'installed/openable content detected' if installed else 'not installed yet; ready to wire as offline/field-kit launcher after setup approval'
        elif sid == 'uptimekuma':
            readiness = 'container running/openable status UI' if unit.get('active') else 'installed but container/service is stopped'
        elif sid == 'docker':
            readiness = 'docker engine available; container actions are status-only here' if unit.get('active') else 'docker installed but service not active'
        elif sid == 'portainer':
            readiness = 'Portainer Docker UI running on 9443' if unit.get('active') else ('Portainer installed but stopped' if installed else 'Portainer not installed yet')
        elif sid == 'hermesworkspace':
            readiness = 'Hermes Workspace open on port 3000' if unit.get('active') else 'Hermes Workspace service/port not active'
        elif sid == 'godseye':
            readiness = 'live Vite server running; high CPU source when left on' if unit.get('active') else 'live server stopped; static fallback still available'
        elif sid in ('jellyfin', 'syncthing'):
            readiness = 'service/UI openable' if unit.get('active') else 'installed but service is stopped'
        elif sid == 'securitylab':
            readiness = 'installed; review/run individual blue-team scripts manually' if installed else 'not installed yet; clone/stage repo, then review hardening/IDS/honeypot/dashboard scripts before any run'
        elif sid in ('homeassistant', 'heimdall', 'conflictly', 'osirisosint', 'leolabsleo'):
            readiness = 'external dashboard/web app link staged; opens in browser only'
        elif sid == 'ruview':
            readiness = 'RuView repo/static UI staged; live sensing needs ESP32 CSI hardware setup/consent' if installed else 'clone RuView and mirror static UI before use'
        elif sid == 'sdrsuite':
            readiness = 'receive-side SDR CLI tools installed; plug RTL-SDR/HackRF/Airspy receiver to start hardware checks' if installed else 'install rtl-sdr/rtl_433/SoapySDR tools'
        elif sid in ('cyberradar','payloadsallthethings','hacktricks','seclists','awesomehacking','awesomebugbounty','hackingtool'):
            readiness = 'local reference clone present; docs/reference only, no auto-run' if installed else 'reference repo not cloned yet'
        else:
            readiness = 'status unknown'
        modules.append({
            **meta,
            'id': sid,
            'enabled': enabled,
            'installed': installed,
            'existing_paths': existing,
            'commands': found,
            'missing_commands': missing,
            'unit': unit,
            'unit_exists': unit_exists,
            'running': bool(unit.get('active')),
            'state': 'enabled/staged' if enabled else 'disabled',
            'readiness': readiness,
            'starts_action': False,
            'last_message': states.get(sid, {}).get('last_message', ''),
        })
    return {
        'mode': 'real tool readiness + safe-gated launch planning',
        'policy': 'Cards report live install/service/command state. Generic toggles stage/enable only; active scans, installs, services, or field-system changes require separate explicit approval and target scope.',
        'modules': modules,
    }


def lab_software_action(module: str, action: str) -> Dict[str, Any]:
    module = str(module or '').strip().lower()
    action = str(action or '').strip().lower()
    if module not in LAB_SOFTWARE_DEFS:
        return {'ok': False, 'error': f'Unknown lab software module {module}', 'software': lab_software_status()}
    if action not in ('enable', 'disable', 'check', 'open', 'install'):
        return {'ok': False, 'error': 'Only enable/disable/check/open/install are supported. Install only clones safe reference content; setup scripts remain manual because they can alter SSH/firewall/services.', 'software': lab_software_status()}
    cfg = _lab_software_config()
    state = cfg.setdefault('lab_software', {}).setdefault(module, {})
    meta = LAB_SOFTWARE_DEFS[module]
    status_before = next((m for m in lab_software_status()['modules'] if m['id'] == module), {})
    if action == 'disable':
        state['enabled'] = False
        if module == 'hermesworkspace':
            cp = _run(['systemctl', '--user', 'stop', 'hermes-workspace.service'], timeout=60)
            state['last_message'] = 'Hermes Workspace stopped.' if cp.returncode == 0 else f"Hermes Workspace stop failed: {(cp.stderr or cp.stdout).strip()[:240]}"
        elif module == 'openwebui':
            cp = _run(['docker', 'stop', 'open-webui'], timeout=120)
            state['last_message'] = 'Open WebUI stopped.' if cp.returncode == 0 else f"Open WebUI stop failed: {(cp.stderr or cp.stdout).strip()[:240]}"
        elif module == 'projectnomad':
            cp = _run(['bash', '-lc', 'cd /home/pi/apps/project-nomad && docker compose -f docker-compose.arm64.yml down'], timeout=240)
            state['last_message'] = 'Project N.O.M.A.D containers stopped.' if cp.returncode == 0 else f"Project N.O.M.A.D stop failed: {(cp.stderr or cp.stdout).strip()[:240]}"
        elif module == 'portainer':
            cp = _run(['docker', 'stop', 'portainer'], timeout=120)
            state['last_message'] = 'Portainer stopped.' if cp.returncode == 0 else f"Portainer stop failed: {(cp.stderr or cp.stdout).strip()[:240]}"
        else:
            state['last_message'] = f"{meta['label']} disabled/reset. No service or scan was started."
    elif action == 'enable':
        state['enabled'] = True
        state['last_message'] = f"{meta['label']} enabled/staged. Live readiness is shown; active use still needs a specific owned-lab target or install approval."
    elif action == 'check':
        state['last_message'] = f"{meta['label']} check complete: {'installed path/unit detected' if status_before.get('installed') else 'not installed yet'}."
    elif action == 'install':
        clone_modules = {'securitylab', 'ruview', 'cyberradar', 'payloadsallthethings', 'hacktricks', 'seclists', 'awesomehacking', 'awesomebugbounty', 'hackingtool'}
        if module == 'sdrsuite':
            state['last_message'] = 'SDR CLI receive tools are installed via apt (rtl-sdr, rtl_433, SoapySDR). SDR++ GUI is source-tracked only; use gqrx/cubicsdr later if you want a Pi GUI receiver.'
        elif module == 'flockcamera':
            state['last_message'] = 'Flock camera repo is not cloned yet because no clear Pi-compatible canonical repo was found. Pick the exact repo and this card can stage it.'
        elif module not in clone_modules:
            state['last_message'] = f"{meta['label']} install is not wired here; use source repo/manual setup."
        elif status_before.get('installed'):
            state['last_message'] = f"{meta['label']} is already present; scripts remain manual/review-first."
        else:
            default_targets = {
                'securitylab': '/home/pi/apps/raspberry-pi-security-lab',
                'ruview': '/home/pi/apps/RuView',
                'cyberradar': '/home/pi/apps/cyberradar',
                'payloadsallthethings': '/home/pi/apps/security-references/PayloadsAllTheThings',
                'hacktricks': '/home/pi/apps/security-references/hacktricks',
                'seclists': '/home/pi/apps/security-references/SecLists',
                'awesomehacking': '/home/pi/apps/security-references/Awesome-Hacking',
                'awesomebugbounty': '/home/pi/apps/security-references/awesome-bug-bounty',
                'hackingtool': '/home/pi/apps/security-references/hackingtool',
                'osirisosint': '/home/pi/apps/security-references/OSIRIS',
            }
            target = Path(default_targets[module])
            target.parent.mkdir(parents=True, exist_ok=True)
            cp = _run(['git', 'clone', '--depth', '1', meta['source'], str(target)], timeout=600)
            if cp.returncode == 0:
                state['last_message'] = f"{meta['label']} cloned to {target}. It is reference/staged content only; no setup scripts or payloads were run."
            else:
                state['last_message'] = f"Clone failed: {(cp.stderr or cp.stdout).strip()[:260]}"
    elif action == 'open':
        state['enabled'] = True
        if module == 'ollama' and status_before.get('installed'):
            cp = _run(['sudo', '-n', 'systemctl', 'start', 'ollama.service'], timeout=60)
            if cp.returncode == 0:
                state['last_message'] = 'Ollama service start requested and should answer at http://127.0.0.1:11434. Use Open WebUI after its UI is installed on a non-conflicting port.'
            else:
                state['last_message'] = f"Ollama start failed: {(cp.stderr or cp.stdout).strip()[:240]}"
        elif module == 'openwebui' and status_before.get('installed'):
            cp = _run(['docker', 'start', 'open-webui'], timeout=120)
            if cp.returncode == 0:
                state['last_message'] = 'Open WebUI container started. Open http://100.75.120.80:3002; stop it from the dashboard when done.'
            else:
                state['last_message'] = f"Open WebUI start failed: {(cp.stderr or cp.stdout).strip()[:240]}"
        elif module == 'projectnomad' and status_before.get('installed'):
            cp = _run(['systemctl', '--user', 'start', 'project-nomad.service'], timeout=300)
            if cp.returncode == 0:
                state['last_message'] = "Project N.O.M.A.D launch requested. Stack should open at http://100.75.120.80:8080 after containers finish warming up; stop it from the dashboard when done."
            else:
                state['last_message'] = f"Project N.O.M.A.D start failed: {(cp.stderr or cp.stdout).strip()[:240]}"
        elif module == 'hermesworkspace' and status_before.get('installed'):
            cp = _run(['systemctl', '--user', 'start', 'hermes-workspace.service'], timeout=120)
            if cp.returncode == 0:
                state['last_message'] = 'Hermes Workspace started. Open http://100.75.120.80:3000; stop it from the dashboard when done.'
            else:
                state['last_message'] = f"Hermes Workspace start failed: {(cp.stderr or cp.stdout).strip()[:240]}"
        elif module == 'portainer' and status_before.get('installed'):
            cp = _run(['docker', 'start', 'portainer'], timeout=120)
            if cp.returncode == 0:
                state['last_message'] = 'Portainer started. Open https://100.75.120.80:9443.'
            else:
                state['last_message'] = f"Portainer start failed: {(cp.stderr or cp.stdout).strip()[:240]}"
        elif module == 'bjorn' and status_before.get('installed'):
            state['last_message'] = "Bjorn is installed in safe/manual staging. Runtime start remains blocked until CAK3D gives an owned-lab target/scope because Bjorn can scan, brute-force, and exfiltrate by design."
        elif module in ('conflictly', 'osirisosint', 'leolabsleo'):
            state['last_message'] = f"{meta['label']} external link is ready: {meta.get('url') or meta.get('source')}. Spac3-Gh0st opens it only; no scraping or automation."
        elif module == 'securitylab' and status_before.get('installed'):
            paths = ', '.join(status_before.get('existing_paths') or [])
            state['last_message'] = f'Raspberry Pi Security Lab is installed at {paths}. Use the Lab card to review scripts; no hardening/IDS/honeypot script is auto-run from Spac3-Gh0st.'
        elif status_before.get('installed'):
            state['last_message'] = f"{meta['label']} is installed/staged. Open/use wiring should target: {', '.join(status_before.get('existing_paths') or [meta['source']])}."
        else:
            state['last_message'] = f"{meta['label']} is not installed on this Pi yet. Source opened as reference; install/run requires separate approval."
    save_config(cfg)
    current = next((m for m in lab_software_status()['modules'] if m['id'] == module), {})
    return {'ok': True, 'module': module, 'action': action, 'message': state['last_message'], 'status': current, 'software': lab_software_status()}


def _spicy_config() -> Dict[str, Any]:
    cfg = load_config()
    state = cfg.setdefault('spicy_tools', {})
    for key in SPICY_TOOL_DEFS:
        state.setdefault(key, {'enabled': False, 'last_message': ''})
    return cfg


def _wifi_has_external_adapter() -> bool:
    usb = _cmd_output(['bash', '-lc', 'lsusb 2>/dev/null'], timeout=4).lower()
    monitorish = ('ralink', 'mediatek', 'realtek', 'ath9k', 'ath10k', 'alfa', 'rtl8812', 'rtl8814', 'rtl8187', 'mediatek')
    return any(token in usb for token in monitorish)

def spicy_tools_status() -> Dict[str, Any]:
    cfg = _spicy_config()
    save_config(cfg)
    state = cfg.setdefault('spicy_tools', {})
    external_adapter = _wifi_has_external_adapter()
    tools = []
    for key, info in SPICY_TOOL_DEFS.items():
        commands = info.get('commands') or []
        found = [c for c in commands if command_exists(c)]
        unit_name = str(info.get('unit') or '')
        unit = _unit_state(unit_name)
        exists = _unit_exists(unit_name) if unit_name else False
        enabled = bool(state.get(key, {}).get('enabled', False))
        installed = bool(found) or exists
        running = bool(unit.get('active'))
        missing = [c for c in commands if c not in found]
        high_risk = info.get('risk') == 'high'
        operational_safe = bool(unit_name and exists and installed and not high_risk)
        if key in ('bettercap', 'aircrack', 'pwnagotchi', 'nexmon') and not external_adapter:
            requirement = 'external monitor/owned-lab adapter not detected; management wlan0 stays untouched'
        elif key == 'p4wnaloha':
            requirement = 'USB gadget payload execution blocked; posture view only'
        elif key == 'honeypi':
            requirement = 'listener exposure blocked until isolated interface/ports are approved'
        else:
            requirement = 'ready for safe service start when installed and configured'
        note_parts = []
        if unit_name:
            note_parts.append(f"unit {unit_name} {unit['active_text']}/{unit['enabled_text']} exists={exists}")
        note_parts.append(', '.join(found) if found else 'commands missing: ' + ', '.join(missing or commands or ['n/a']))
        if enabled and not running:
            note_parts.append('dashboard enabled/staged')
        tools.append({
            'id': key, 'label': info['label'], 'installed': installed, 'commands': found,
            'missing_commands': missing, 'enabled': enabled, 'running': running,
            'unit': unit, 'unit_exists': exists, 'risk': info['risk'],
            'mode': info['mode'], 'description': info['description'],
            'can_enable': not running, 'can_disable': running or enabled,
            'operational_safe': operational_safe,
            'hardware_ready': external_adapter if key in ('bettercap', 'aircrack', 'pwnagotchi', 'nexmon') else True,
            'requirement': requirement,
            'blocked_actions': ['deauth', 'injection', 'credential capture', 'cracking', 'MITM/spoofing'],
            'status_note': ' // '.join(note_parts),
        })
    return {'mode': 'defensive-only', 'policy': 'Enable starts only operational-safe installed services. Missing/high-risk modules stage readiness and never run capture/deauth/injection/cracking/MITM from this button.', 'tools': tools}

def spicy_tool_action(tool: str, action: str) -> Dict[str, Any]:
    tool = str(tool or '').strip().lower()
    action = str(action or '').strip().lower()
    if tool not in SPICY_TOOL_DEFS:
        return {'ok': False, 'error': f'unknown spicy tool {tool}', **spicy_tools_status()}
    if action not in ('enable', 'disable', 'reset'):
        return {'ok': False, 'error': f'unsupported action {action}', **spicy_tools_status()}
    info = SPICY_TOOL_DEFS[tool]
    unit = str(info.get('unit') or '')
    risk = str(info.get('risk') or '')
    commands = info.get('commands') or []
    found = [c for c in commands if command_exists(c)]
    installed = bool(found) or _unit_exists(unit)
    cfg = _spicy_config()
    tool_state = cfg.setdefault('spicy_tools', {}).setdefault(tool, {})
    results = []
    if action == 'enable':
        tool_state['enabled'] = True
        # Only medium/low-risk services are actually started. High-risk RF/USB tooling is staged as ready/readiness-only.
        if unit and installed and risk != 'high' and _unit_exists(unit):
            cp = _run(['sudo', '-n', 'systemctl', 'start', unit], timeout=25)
            results.append({'cmd': f'systemctl start {unit}', 'exit_code': cp.returncode, 'stderr': cp.stderr.strip()[:240]})
            ok = cp.returncode == 0
            msg = f'{info["label"]} operational-safe service start attempted.' if ok else f'{info["label"]} is enabled in dashboard, but service start failed.'
        elif installed:
            ok = True
            msg = f'{info["label"]} enabled/staged. Installed tooling is detected, but runtime is readiness-only until exact owned-lab hardware/mode is available.'
        else:
            ok = True
            msg = f'{info["label"]} enabled/staged. Missing: {", ".join(commands or ["service/tool wrapper"])}. Install/setup is still blocked until requested.'
        tool_state['last_message'] = msg
        save_config(cfg)
        return {'ok': ok, 'message': msg, 'results': results, **spicy_tools_status()}
    if action in ('disable', 'reset'):
        if unit and _unit_exists(unit):
            cp = _run(['sudo', '-n', 'systemctl', 'stop', unit], timeout=25)
            results.append({'cmd': f'systemctl stop {unit}', 'exit_code': cp.returncode, 'stderr': cp.stderr.strip()[:240]})
        tool_state['enabled'] = False
        tool_state['last_message'] = 'disabled/reset; service stopped only if a safe known unit existed'
        save_config(cfg)
        return {'ok': True, 'message': 'safe disabled/reset complete; no risky action was started', 'results': results, **spicy_tools_status()}
    return {'ok': False, 'error': 'unhandled action', **spicy_tools_status()}


SERVICE_MAP = {
    'vnc': {'unit': 'wayvnc.service', 'label': 'RealVNC/VNC', 'url': 'vnc://{tailscale}:5900'},
    'syncthing': {'unit': 'syncthing@pi.service', 'label': 'Syncthing', 'url': 'http://{tailscale}:8384'},
}


def _systemctl(unit: str, action: str) -> subprocess.CompletedProcess[str]:
    return _run(['sudo', '-n', 'systemctl', action, unit], timeout=25)



FLIPPER_FEATURE_DEFS = {
    'ir_library': {'label': 'IR Library Viewer', 'description': 'Catalog .ir remotes/notes if files are added; no transmit path.', 'requires_hardware': False},
    'subghz_catalog': {'label': 'Sub-GHz File Catalog', 'description': 'Read-only .sub inventory/reference cards; no replay, emulate, or capture.', 'requires_hardware': False},
    'nfc_rfid_notes': {'label': 'NFC/RFID Notes', 'description': 'Organize tag notes and compatibility info; no write/clone actions.', 'requires_hardware': False},
    'badusb_viewer': {'label': 'BadUSB Payload Viewer', 'description': 'View payload names/risk notes only; no run button and no HID injection.', 'requires_hardware': False},
    'usb_dock_status': {'label': 'USB Dock Status', 'description': 'Detect plugged Flipper/qFlipper tooling when present.', 'requires_hardware': False},
}


def _flipper_feature_config() -> Dict[str, Any]:
    cfg = load_config()
    lab = cfg.setdefault('lab_toys', {})
    fl = lab.setdefault('flipper_features', {})
    for feature_id in FLIPPER_FEATURE_DEFS:
        fl.setdefault(feature_id, {'enabled': False})
    return cfg


def flipper_zero_status() -> Dict[str, Any]:
    usb = _cmd_output(['bash', '-lc', 'lsusb 2>/dev/null'], timeout=4)
    lower = usb.lower()
    connected = any(token in lower for token in ('flipper', '0483:5740', '0483:df11'))
    tools = {name: command_exists(name) for name in ('qFlipper', 'flipper', 'dfu-util', 'serial', 'screen')}
    cfg = _flipper_feature_config()
    feature_cfg = cfg.get('lab_toys', {}).get('flipper_features', {})
    features = []
    for feature_id, meta in FLIPPER_FEATURE_DEFS.items():
        features.append({
            'id': feature_id,
            **meta,
            'enabled': bool(feature_cfg.get(feature_id, {}).get('enabled', False)),
            'can_enable': True,
            'safe_mode': 'dashboard/reference only',
        })
    return {
        'connected': connected,
        'usb_matches': [line for line in usb.splitlines() if any(t in line.lower() for t in ('flipper', '0483:5740', '0483:df11'))],
        'tools': tools,
        'mode': 'safe dock / disabled-by-default feature toggles',
        'features': features,
        'ideas': [
            'IR/sub-GHz/NFC/RFID file inventory viewer when a Flipper is plugged in',
            'Read-only firmware/tool version panel using qFlipper/flipper CLI when installed',
            'Signal library catalog cards; transmit/emulate actions stay disabled until explicit physical approval',
            'BadUSB payload library viewer only; no auto-run or injection from Spac3-Gh0st',
        ],
        'blocked_actions': ['transmit', 'emulate', 'badusb run', 'subghz attack', 'rfid/nfc write'],
    }


def flipper_feature_action(feature: str, action: str) -> Dict[str, Any]:
    feature = str(feature or '').strip().lower()
    action = str(action or '').strip().lower()
    if feature not in FLIPPER_FEATURE_DEFS:
        return {'ok': False, 'error': f'Unknown Flipper-inspired feature {feature}', 'flipper': flipper_zero_status()}
    if action not in ('enable', 'disable'):
        return {'ok': False, 'error': 'Only enable/disable are supported; both are dashboard-safe toggles.', 'flipper': flipper_zero_status()}
    cfg = _flipper_feature_config()
    cfg.setdefault('lab_toys', {}).setdefault('flipper_features', {}).setdefault(feature, {})['enabled'] = action == 'enable'
    save_config(cfg)
    state = 'enabled' if action == 'enable' else 'disabled'
    return {'ok': True, 'message': f'{FLIPPER_FEATURE_DEFS[feature]["label"]} {state} in safe reference mode only.', 'flipper': flipper_zero_status()}

LAB_GATE_DEFS = {
    'pi5_optical_audio': {
        'label': 'Pi5 Optical Audio GPIO12',
        'description': 'Stage RASPIAUDIO GPIO S/PDIF driver/install workflow for later hardware wiring. Does not install modules or output audio.',
        'blocked_actions': ['kernel module install', 'boot autoload', 'GPIO12 audio output', 'reboot'],
    },
    'piaware_adsb': {
        'label': 'PiAware / ADS-B Receiver',
        'description': 'Stage PiAware/dump1090/readsb install and ADS-B receiver checklist. Does not install packages, claim feeder, or start SDR capture.',
        'blocked_actions': ['package install', 'service enable/start', 'claim feeder', 'RTL-SDR capture'],
    },
}


def _lab_gate_config() -> Dict[str, Any]:
    cfg = load_config()
    lab = cfg.setdefault('lab_toys', {})
    gates = lab.setdefault('blocked_gates', {})
    for gate_id in LAB_GATE_DEFS:
        gates.setdefault(gate_id, {'enabled': False})
    return cfg


def lab_gate_status(gate_id: str) -> Dict[str, Any]:
    cfg = _lab_gate_config()
    gate = cfg.get('lab_toys', {}).get('blocked_gates', {}).get(gate_id, {})
    meta = LAB_GATE_DEFS.get(gate_id, {})
    return {
        'id': gate_id,
        'label': meta.get('label', gate_id),
        'description': meta.get('description', ''),
        'enabled': bool(gate.get('enabled', False)),
        'home_lab_enabled': bool(gate.get('enabled', False)),
        'can_enable': True,
        'can_disable': True,
        'mode': 'operational-safe home-lab toggle',
        'blocked_actions': meta.get('blocked_actions', []),
        'note': 'Enable tries safe operational behavior only when supporting software/services already exist. Missing/hardware-blocked modules stay staged and report what is needed.',
    }


def lab_gate_action(gate: str, action: str) -> Dict[str, Any]:
    gate = str(gate or '').strip().lower()
    action = str(action or '').strip().lower()
    if gate not in LAB_GATE_DEFS:
        return {'ok': False, 'error': f'Unknown lab gate {gate}', 'gates': {gid: lab_gate_status(gid) for gid in LAB_GATE_DEFS}}
    if action not in ('enable', 'disable'):
        return {'ok': False, 'error': 'Only enable/disable are supported.', 'gate': lab_gate_status(gate)}
    cfg = _lab_gate_config()
    cfg.setdefault('lab_toys', {}).setdefault('blocked_gates', {}).setdefault(gate, {})['enabled'] = action == 'enable'
    results = []
    if gate == 'piaware_adsb' and action == 'enable':
        # If PiAware/readsb/dump1090 are installed later, try safe service starts; current missing state just stages readiness.
        for unit in ('readsb', 'dump1090-fa', 'piaware'):
            if _unit_exists(unit):
                cp = _run(['sudo', '-n', 'systemctl', 'start', unit], timeout=25)
                results.append({'cmd': f'systemctl start {unit}', 'exit_code': cp.returncode, 'stderr': cp.stderr.strip()[:240]})
    if gate == 'piaware_adsb' and action == 'disable':
        for unit in ('piaware', 'dump1090-fa', 'readsb'):
            if _unit_exists(unit):
                cp = _run(['sudo', '-n', 'systemctl', 'stop', unit], timeout=25)
                results.append({'cmd': f'systemctl stop {unit}', 'exit_code': cp.returncode, 'stderr': cp.stderr.strip()[:240]})
    # Optical audio remains dashboard/readiness only: driver install, GPIO12 output, and reboot require separate wiring approval.
    save_config(cfg)
    state = 'enabled' if action == 'enable' else 'disabled'
    if gate == 'pi5_optical_audio':
        msg = f'{LAB_GATE_DEFS[gate]["label"]} {state}. Readiness is armed only; no kernel module install, GPIO12 output, boot autoload, or reboot was performed.'
    elif results:
        msg = f'{LAB_GATE_DEFS[gate]["label"]} {state}; safe installed service operations attempted.'
    else:
        msg = f'{LAB_GATE_DEFS[gate]["label"]} {state}/staged. Required packages/services are not installed yet, so no runtime action was performed.'
    return {'ok': True, 'message': msg, 'results': results, 'gate': lab_gate_status(gate)}



SAFETY_BOUNDARY_DEFS = {
    'monitor_mode': {
        'label': 'Monitor Mode',
        'summary': 'Use a separate monitor interface for RF visibility without touching management wlan0.',
        'used_by': ['Pwnagotchi posture', 'Kali Wi-Fi toolbelt', 'Bettercap readiness', 'Passive Capture'],
        'needed_hardware': ['external USB Wi-Fi adapter with monitor support', 'keep wlan0 managed for SSH/Tailscale'],
        'needed_software': ['iw', 'airmon-ng or manual iw workflow', 'compatible driver/firmware'],
        'service_or_tool': 'iw / airmon-ng; no service started by this toggle',
        'safe_when_enabled': 'safe workflow armed: tool checks, evidence panel, and wlan0/Tailscale protection stay active' ,
        'blocked_actions': ['switching wlan0 to monitor', 'disconnecting SSH/Tailscale', 'injection/deauth'],
    },
    'packet_injection': {
        'label': 'Packet Injection',
        'summary': 'Lab-only frame injection capability check for compatible adapters.',
        'used_by': ['Kali Wi-Fi toolbelt', 'Bettercap', 'Pwnagotchi-style lab work'],
        'needed_hardware': ['external injection-capable USB Wi-Fi adapter', 'isolated CAK3D-owned lab target'],
        'needed_software': ['aireplay-ng or bettercap caplet', 'monitor-mode interface'],
        'service_or_tool': 'aireplay-ng / bettercap; not launched by this toggle',
        'safe_when_enabled': 'staged only; shows needed adapter/tool state',
        'blocked_actions': ['actual injection', 'third-party networks', 'unspecified target traffic'],
    },
    'deauth': {
        'label': 'Deauth',
        'summary': 'Owned-lab deauthentication testing boundary.',
        'used_by': ['Pwnagotchi', 'Bettercap', 'Kali Wi-Fi toolbelt'],
        'needed_hardware': ['external monitor/injection adapter', 'lab AP/client you own'],
        'needed_software': ['aireplay-ng or bettercap', 'selected BSSID/channel', 'owned-lab mode'],
        'service_or_tool': 'aireplay-ng --deauth / bettercap wifi.deauth; blocked here',
        'safe_when_enabled': 'permission/readiness flag only; no frames are sent',
        'blocked_actions': ['sending deauth frames', 'client disruption', 'third-party networks'],
    },
    'passive_capture': {
        'label': 'Passive Capture',
        'summary': 'Listen-only capture for owned-lab monitoring when a monitor adapter exists.',
        'used_by': ['Pwnagotchi posture', 'RF Audit', 'Kali Wi-Fi toolbelt'],
        'needed_hardware': ['external monitor-mode adapter', 'storage for pcap files'],
        'needed_software': ['airodump-ng or tcpdump/tshark', 'monitor-mode interface'],
        'service_or_tool': '/api/pwnagotchi/capture handles this separately with owned_lab=true',
        'safe_when_enabled': 'staged only; the separate capture endpoint still enforces owned_lab + monitor interface',
        'blocked_actions': ['auto-start capture', 'capturing third-party traffic', 'credential collection'],
    },
    'credential_capture': {
        'label': 'Credential Capture',
        'summary': 'Hard boundary for credential interception/collection features.',
        'used_by': ['Bettercap', 'honeypot ideas', 'MITM/spoofing'],
        'needed_hardware': ['isolated lab network only'],
        'needed_software': ['explicit lab service wrapper', 'logging redaction policy'],
        'service_or_tool': 'not implemented as a runtime action',
        'safe_when_enabled': 'documentation/readiness only; dashboard does not collect secrets',
        'blocked_actions': ['credential harvesting', 'phishing', 'secret display/storage'],
    },
    'hash_cracking': {
        'label': 'Hash Cracking',
        'summary': 'Crack captured lab handshakes only after separate job approval.',
        'used_by': ['Kali Wi-Fi toolbelt', 'Pwnagotchi artifacts'],
        'needed_hardware': ['CPU/GPU capacity optional', 'captured authorized handshake file'],
        'needed_software': ['aircrack-ng or hashcat', 'wordlist/rules'],
        'service_or_tool': 'aircrack-ng/hashcat job; not launched here',
        'safe_when_enabled': 'staged only; no cracking job is started',
        'blocked_actions': ['starting cracking jobs', 'using non-owned hashes', 'printing recovered passwords'],
    },
    'mitm_spoofing': {
        'label': 'MITM / Spoofing',
        'summary': 'Boundary for ARP/DNS/traffic interception lab modules.',
        'used_by': ['Bettercap', 'Security Onion ideas'],
        'needed_hardware': ['isolated lab subnet', 'router/AP you control'],
        'needed_software': ['bettercap caplets', 'explicit lab target config'],
        'service_or_tool': 'bettercap; unsafe caplets blocked here',
        'safe_when_enabled': 'staged only; no spoofing or interception begins',
        'blocked_actions': ['ARP spoofing', 'DNS spoofing', 'MITM proxying', 'credential capture'],
    },
    'badusb_hid': {
        'label': 'BadUSB / HID Injection',
        'summary': 'USB gadget payload boundary inspired by P4wnP1/Flipper workflows.',
        'used_by': ['P4wnP1 A.L.O.H.A posture', 'Flipper-inspired BadUSB viewer'],
        'needed_hardware': ['USB gadget-capable device', 'physical target you own'],
        'needed_software': ['payload library viewer', 'separate signed run approval'],
        'service_or_tool': 'viewer/reference only; payload runner not exposed',
        'safe_when_enabled': 'library/readiness view only',
        'blocked_actions': ['typing payloads', 'HID injection', 'auto-run scripts'],
    },
    'rf_transmit_emulation': {
        'label': 'RF Transmit / Emulation',
        'summary': 'Boundary for IR/sub-GHz/NFC/RFID replay or emulation.',
        'used_by': ['Flipper-inspired modules', 'Sub-GHz catalog', 'NFC/RFID notes'],
        'needed_hardware': ['appropriate RF/IR/NFC hardware', 'legal/owned target device'],
        'needed_software': ['read-only library first', 'separate transmit wrapper if ever approved'],
        'service_or_tool': 'no transmit/emulate service exists in dashboard',
        'safe_when_enabled': 'readiness/catalog mode only',
        'blocked_actions': ['transmit', 'replay', 'emulate', 'jam/interfere'],
    },
    'nfc_rfid_write': {
        'label': 'NFC / RFID Write',
        'summary': 'Boundary for tag write/clone operations.',
        'used_by': ['Flipper-inspired NFC/RFID notes', 'inventory/tag experiments'],
        'needed_hardware': ['writer hardware', 'blank/owned tags'],
        'needed_software': ['read-only tag notes now', 'separate writer tool later'],
        'service_or_tool': 'not implemented as runtime action',
        'safe_when_enabled': 'notes/catalog readiness only',
        'blocked_actions': ['write', 'clone', 'emulate', 'overwrite tags'],
    },
    'gpio12_audio_output': {
        'label': 'GPIO12 Optical Audio Output',
        'summary': 'Pi 5 GPIO S/PDIF output boundary.',
        'used_by': ['Pi5 Optical Audio panel'],
        'needed_hardware': ['GPIO12 physical pin 32 + GND wiring', 'LED/TOSLINK transmitter stage'],
        'needed_software': ['RASPIAUDIO raspiaudio_spdif_pio module', 'ALSA RASPISPDIF card', '48 kHz stereo source'],
        'service_or_tool': 'kernel module + ALSA card; not installed/loaded here',
        'safe_when_enabled': 'readiness armed only; no GPIO output',
        'blocked_actions': ['drive GPIO12', 'load module', 'autoload at boot', 'reboot'],
    },
    'kernel_module_reboot': {
        'label': 'Kernel Module Install / Reboot',
        'summary': 'Boundary for kernel/boot-level changes.',
        'used_by': ['Pi5 Optical Audio', 'Nexmon/driver work'],
        'needed_hardware': ['confirmed board/adapter target', 'rollback console path'],
        'needed_software': ['kernel headers', 'build tools', 'known-good backup'],
        'service_or_tool': 'apt/make/modprobe/reboot; not run by dashboard toggle',
        'safe_when_enabled': 'approval/readiness flag only',
        'blocked_actions': ['apt install kernel pieces', 'modprobe', 'boot config edits', 'reboot'],
    },
}


def _safety_boundary_config() -> Dict[str, Any]:
    cfg = load_config()
    lab = cfg.setdefault('lab_toys', {})
    boundaries = lab.setdefault('safety_boundaries', {})
    for boundary_id in SAFETY_BOUNDARY_DEFS:
        boundaries.setdefault(boundary_id, {'enabled': False})
    return cfg


def safety_boundary_status() -> Dict[str, Any]:
    cfg = _safety_boundary_config()
    save_config(cfg)
    states = cfg.get('lab_toys', {}).get('safety_boundaries', {})
    tools = {
        name: command_exists(name)
        for name in ('iw', 'airmon-ng', 'aircrack-ng', 'aireplay-ng', 'airodump-ng', 'bettercap', 'hashcat', 'hcxdumptool', 'hcxpcapngtool', 'qFlipper', 'flipper', 'dfu-util', 'rtl_sdr')
    }
    wifi = _cmd_output(['bash', '-lc', 'iw dev 2>/dev/null || /usr/sbin/iw dev 2>/dev/null || true'], timeout=4)
    usb = _cmd_output(['bash', '-lc', 'lsusb 2>/dev/null'], timeout=4)
    external_adapter = _wifi_has_external_adapter()
    cards = []
    for boundary_id, meta in SAFETY_BOUNDARY_DEFS.items():
        enabled = bool(states.get(boundary_id, {}).get('enabled', False))
        if boundary_id in ('monitor_mode', 'packet_injection', 'deauth', 'passive_capture'):
            readiness = 'external adapter detected' if external_adapter else 'needs external monitor/injection adapter; wlan0 remains managed'
        elif boundary_id in ('gpio12_audio_output', 'kernel_module_reboot'):
            readiness = 'Pi5/GPIO readiness panel available; install/output/reboot still blocked'
        elif boundary_id in ('badusb_hid', 'rf_transmit_emulation', 'nfc_rfid_write'):
            readiness = 'reference/catalog mode only; hardware action blocked'
        else:
            readiness = 'policy boundary staged; runtime action not implemented from generic toggle'
        cards.append({
            'id': boundary_id,
            'enabled': enabled,
            'state': 'enabled/staged' if enabled else 'disabled',
            'can_enable': True,
            'can_disable': True,
            'risk': 'high',
            'starts_action': False,
            'mode': 'safe/gated workflow',
            'readiness': readiness,
            **meta,
        })
    return {
        'mode': 'disabled-by-default safety boundaries',
        'policy': 'These toggles arm/stage requirements only. They never start offensive RF/USB/GPIO/kernel actions.',
        'external_monitor_adapter_detected': external_adapter,
        'wlan0_policy': 'wlan0 stays managed for SSH/Tailscale/dashboard',
        'tools': tools,
        'wifi_summary': wifi[:1200],
        'usb_summary': usb[:1200],
        'boundaries': cards,
    }


def safety_boundary_action(boundary: str, action: str) -> Dict[str, Any]:
    boundary = str(boundary or '').strip().lower()
    action = str(action or '').strip().lower()
    if boundary not in SAFETY_BOUNDARY_DEFS:
        return {'ok': False, 'error': f'Unknown safety boundary {boundary}', 'safety_boundaries': safety_boundary_status()}
    if action not in ('enable', 'disable'):
        return {'ok': False, 'error': 'Only enable/disable are supported. This endpoint never starts RF/USB/GPIO/kernel actions.', 'safety_boundaries': safety_boundary_status()}
    cfg = _safety_boundary_config()
    cfg.setdefault('lab_toys', {}).setdefault('safety_boundaries', {}).setdefault(boundary, {})['enabled'] = action == 'enable'
    save_config(cfg)
    state = 'enabled/staged' if action == 'enable' else 'disabled'
    label = SAFETY_BOUNDARY_DEFS[boundary]['label']
    return {
        'ok': True,
        'message': f'{label} {state}. Safe workflow evidence is live. High-risk actions still require explicit owned-lab target/setup and are not launched by this generic boundary toggle.',
        'boundary': next((b for b in safety_boundary_status()['boundaries'] if b['id'] == boundary), {}),
        'safety_boundaries': safety_boundary_status(),
        'workflows': lab_workflows_status(),
    }

def pi5_spdif_gpio_status() -> Dict[str, Any]:
    try:
        model = Path('/proc/device-tree/model').read_bytes().replace(b'\x00', b'').decode('utf-8', 'replace').strip()
    except Exception:
        model = _cmd_output(['uname', '-m'], timeout=3)
    kernel = _cmd_output(['uname', '-r'], timeout=3)
    aplay_cards = _cmd_output(['bash', '-lc', 'aplay -l 2>/dev/null'], timeout=5)
    gpio12 = _cmd_output(['bash', '-lc', 'pinctrl get 12 2>&1 || raspi-gpio get 12 2>&1 || true'], timeout=4)
    module = _cmd_output(['bash', '-lc', 'modinfo raspiaudio_spdif_pio 2>/dev/null | sed -n "1,8p"'], timeout=4)
    lsmod = _cmd_output(['bash', '-lc', 'lsmod | grep -E "(^rp1_pio|raspiaudio_spdif|snd)" | sed -n "1,40p"'], timeout=4)
    headers = _cmd_output(['bash', '-lc', 'dpkg -l linux-headers-rpi-2712 2>/dev/null | awk "/^ii/{print $2\" \"$3}"'], timeout=4)
    return {
        'pi5': 'raspberry pi 5' in model.lower(),
        'model': model,
        'kernel': kernel,
        'gpio': 'GPIO12 physical pin 32',
        'gpio12_state': gpio12,
        'rp1_pio_loaded': 'rp1_pio' in lsmod,
        'spdif_module_installed': bool(module),
        'raspispdif_card': 'RASPISPDIF' in aplay_cards,
        'camilladsp_clone': Path.home().joinpath('CamillaDSP').exists(),
        'headers': headers or 'not detected',
        'tools': {name: command_exists(name) for name in ('git', 'make', 'gcc', 'aplay', 'ffmpeg', 'dkms')},
        'install_gated': True,
        'recommended_path': 'RASPIAUDIO CamillaDSP prototypes/pi5_spdif_gpio ALSA kernel module; 48 kHz stereo S16_LE/S32_LE only; GPIO12 raw 3.3V output.',
        'wiring_warning': 'Needs LED/TOSLINK receiver or proper optical transmitter stage on GPIO12 + GND. Do not connect raw GPIO to unknown equipment.',
        'source': 'https://github.com/RASPIAUDIO/CamillaDSP/tree/main/prototypes/pi5_spdif_gpio',
        'blocked_actions': ['kernel module install', 'boot autoload', 'GPIO12 audio output', 'reboot'],
        'gate': lab_gate_status('pi5_optical_audio'),
    }


def piaware_status() -> Dict[str, Any]:
    usb = _cmd_output(['bash', '-lc', 'lsusb 2>/dev/null'], timeout=4)
    lower = usb.lower()
    rtl_tokens = ('0bda:2832', '0bda:2838', 'rtl2832', 'rtl-sdr', 'flightaware', 'ads-b', 'adsb')
    rtl_visible = any(token in lower for token in rtl_tokens)
    tools = {name: command_exists(name) for name in ('piaware', 'dump1090-fa', 'readsb', 'rtl_test', 'rtl_sdr', 'piaware-config', 'view1090-fa')}
    services = {}
    for unit in ('piaware', 'dump1090-fa', 'readsb'):
        active = _cmd_output(['systemctl', 'is-active', unit], timeout=3) or 'inactive'
        enabled = _cmd_output(['systemctl', 'is-enabled', unit], timeout=3) or 'inactive'
        services[unit] = {'active': active == 'active', 'active_text': active, 'enabled_text': enabled}
    ports = _cmd_output(['bash', '-lc', 'ss -ltnp 2>/dev/null | grep -E ":(8080|8081|30003|30005|30104|8754)" || true'], timeout=4)
    web_links = []
    ts = tailscale_ip()
    if ts:
        web_links.extend([
            {'label': 'dump1090 / SkyAware local', 'url': f'http://{ts}:8080/'},
            {'label': 'PiAware status', 'url': f'http://{ts}:8754/'},
        ])
    return {
        'installed': any(tools.values()),
        'rtl_sdr_visible': rtl_visible,
        'usb_matches': [line for line in usb.splitlines() if any(t in line.lower() for t in rtl_tokens)],
        'tools': tools,
        'services': services,
        'ports': ports.splitlines(),
        'web_links': web_links,
        'mode': 'ADS-B/PiAware readiness; receiver services disabled unless approved/configured',
        'install_gated': True,
        'blocked_actions': ['package install', 'service enable/start', 'claim feeder', 'RTL-SDR capture'],
        'gate': lab_gate_status('piaware_adsb'),
        'notes': ['No RTL-SDR was visible in lsusb during the readiness check.' if not rtl_visible else 'RTL-SDR-like USB device detected.', 'PiAware usually needs piaware + dump1090-fa/readsb + receiver/antenna setup.'],
    }



LAB_WORKFLOW_DEFS = {
    'pwnagotchi_handshakes': {
        'label': 'Pwnagotchi Handshake Workflow',
        'source': 'https://pwnagotchi.ai/intro/',
        'summary': 'Real Pwnagotchi-style lifecycle planning: AI posture, passive/owned-lab capture readiness, handshakes directory, plugins, and service state.',
        'used_by': ['Pwnagotchi posture', 'Kali Wi-Fi toolbelt', 'Hashcat WPA/WPA2 workflow'],
        'needed': ['pwnagotchi package/service', 'external monitor-mode adapter', 'owned_lab=true capture request', 'handshakes output directory'],
        'blocked_actions': ['auto deauth', 'auto capture', 'monitor-mode change on wlan0', 'credential capture'],
    },
    'hashcat_wpa': {
        'label': 'Hashcat WPA/WPA2 Workflow',
        'source': 'https://hashcat.net/wiki/doku.php?id=cracking_wpawpa2',
        'summary': 'WPA/WPA2 cracking pipeline readiness: capture artifact inventory, hcxpcapngtool conversion, hashcat presence, wordlist/job boundary.',
        'used_by': ['Kali Wi-Fi toolbelt', 'Pwnagotchi artifacts'],
        'needed': ['authorized handshake file', 'hcxpcapngtool', 'hashcat or aircrack-ng', 'wordlist/rules', 'separate cracking job approval'],
        'blocked_actions': ['starting cracking jobs', 'using non-owned hashes', 'printing recovered passwords'],
    },
}


def _lab_workflow_config() -> Dict[str, Any]:
    cfg = load_config()
    workflows = cfg.setdefault('lab_workflows', {})
    for wid in LAB_WORKFLOW_DEFS:
        workflows.setdefault(wid, {'enabled': False})
    return cfg


def lab_workflows_status() -> Dict[str, Any]:
    cfg = _lab_workflow_config()
    save_config(cfg)
    states = cfg.get('lab_workflows', {})
    handshakes_dir = Path('/home/pi/handshakes')
    if not handshakes_dir.exists():
        handshakes_dir = Path('/home/pi/spac3-gh0st/data/handshakes')
    captures = []
    try:
        captures = sorted([p.name for p in handshakes_dir.glob('*') if p.suffix.lower() in ('.pcap', '.pcapng', '.cap', '.22000', '.hc22000')])[-8:]
    except Exception:
        captures = []
    tools = {name: command_exists(name) for name in ('pwnagotchi', 'bettercap', 'airmon-ng', 'airodump-ng', 'aireplay-ng', 'hcxdumptool', 'hcxpcapngtool', 'hashcat', 'aircrack-ng')}
    services = {}
    for unit in ('pwnagotchi', 'bettercap'):
        active = _cmd_output(['systemctl', 'is-active', unit], timeout=3) or 'inactive'
        enabled = _cmd_output(['systemctl', 'is-enabled', unit], timeout=3) or 'inactive'
        services[unit] = {'active': active == 'active', 'active_text': active, 'enabled_text': enabled, 'unit_exists': _unit_exists(unit)}
    external_adapter = _wifi_has_external_adapter()
    cards = []
    for wid, meta in LAB_WORKFLOW_DEFS.items():
        enabled = bool(states.get(wid, {}).get('enabled', False))
        if wid == 'pwnagotchi_handshakes':
            readiness = 'ready for separate owned-lab passive capture endpoint' if external_adapter and (tools.get('pwnagotchi') or tools.get('airodump-ng')) else 'needs external monitor adapter and Pwnagotchi/airodump tooling; wlan0 stays managed'
        else:
            readiness = 'capture artifacts available for separate approved cracking job' if captures and (tools.get('hashcat') or tools.get('aircrack-ng')) else 'needs authorized capture artifact plus hashcat/aircrack workflow'
        cards.append({
            'id': wid,
            'enabled': enabled,
            'state': 'enabled/staged' if enabled else 'disabled',
            'mode': 'readiness/workflow only',
            'starts_action': False,
            'readiness': readiness,
            **meta,
        })
    return {
        'mode': 'owned-lab workflow readiness',
        'policy': 'Panels prepare real Pwnagotchi/Hashcat workflows but do not start capture, deauth, conversion, cracking, monitor mode, or credential handling.',
        'handshakes_dir': str(handshakes_dir),
        'capture_artifacts': captures,
        'tools': tools,
        'services': services,
        'external_monitor_adapter_detected': external_adapter,
        'workflows': cards,
    }


def companion_firmware_action(companion: str, action: str) -> Dict[str, Any]:
    companion = str(companion or '').strip().lower()
    action = str(action or '').strip().lower()
    if action not in ('activate', 'check', 'detect'):
        return {'ok': False, 'error': 'Only activate/check/detect are supported for companion modules.'}
    serials = sorted(str(p) for p in list(Path('/dev').glob('ttyACM*')) + list(Path('/dev').glob('ttyUSB*')))
    usb = _cmd_output(['bash', '-lc', 'lsusb 2>/dev/null'], timeout=4)
    esp_lines = [line for line in usb.splitlines() if any(tok in line.lower() for tok in ('303a:', '10c4:', '1a86:55d4', 'esp', 'silicon labs', 'cp210', 'ch340'))]
    if companion == 'wirelesswizard':
        wifi = _cmd_output(['bash', '-lc', 'iw dev 2>/dev/null || /usr/sbin/iw dev 2>/dev/null || true'], timeout=4)
        return {
            'ok': True, 'companion': companion, 'action': action,
            'message': 'WirelessWizard home activated: Wi-Fi scan/RF Audit panels now own this workflow; no interface mode changes were made.',
            'interfaces_seen': wifi[:1200], 'rf_audit_hint': 'Use the Wi-Fi card Scan button and RF Audit card for channel/adapter state.',
        }
    if companion in ('bruce', 'marauder'):
        found = bool(serials or esp_lines)
        return {
            'ok': True, 'companion': companion, 'action': action, 'esp32_detected': found,
            'serial_candidates': serials, 'usb_matches': esp_lines,
            'message': (f'{companion} companion check found ESP32/serial candidate(s). Open Vision/Companion Firmware before flashing.' if found else f'{companion} companion check complete: no ESP32 USB serial device is visible yet.'),
            'blocked_actions': ['flash without explicit approval', 'deauth/injection/cracking', 'non-owned RF activity'],
        }
    return {'ok': False, 'error': f'Unknown companion module {companion}'}

def nfc_rfid_status() -> Dict[str, Any]:
    crowpi_refs = [
        '/home/pi/Desktop/CrowPi/QA.py',
        '/home/pi/Desktop/CrowPi/MFRC522.py',
        '/home/pi/Desktop/CrowPi/Minecraft/nfc_block_read.py',
        '/home/pi/Desktop/CrowPi/Minecraft/nfc_block_writer.py',
    ]
    refs = [p for p in crowpi_refs if Path(p).exists()]
    imports = {}
    for mod in ('mfrc522', 'RPi.GPIO', 'spidev'):
        cp = _run(['python3', '-c', f'import {mod}; print("ok")'], timeout=6)
        imports[mod] = cp.returncode == 0
    spi_devs = sorted(str(p) for p in Path('/dev').glob('spidev*'))
    usb = _cmd_output(['bash', '-lc', 'lsusb 2>/dev/null'], timeout=4)
    usb_matches = [line for line in usb.splitlines() if any(tok in line.lower() for tok in ('pn532', 'acr122', 'proxmark', 'flipper', 'rfid', 'nfc'))]
    ready = bool(refs and imports.get('mfrc522') and imports.get('spidev') and spi_devs)
    return {
        'ok': True,
        'ready': ready,
        'reader': 'MFRC522/RC522 via CrowPi SPI library' if ready else 'not ready',
        'crowpi_references': refs,
        'python_imports': imports,
        'spi_devices': spi_devs,
        'usb_matches': usb_matches,
        'read_action': 'bounded 8s tag read via mfrc522.SimpleMFRC522; shows UID/text only after you tap Read and present an owned tag',
        'write_action': 'bounded 8s text write via mfrc522.SimpleMFRC522.write; only for owned/blank tags after explicit prompt',
        'blocked_actions': ['clone/emulate/write unknown tags', 'credential/payment/access-card attacks', 'unbounded blocking reader loops'],
    }


def ir_status() -> Dict[str, Any]:
    lirc_devs = sorted(str(p) for p in Path('/dev').glob('lirc*'))
    gpiochips = sorted(str(p) for p in Path('/dev').glob('gpiochip*'))
    tools = {name: command_exists(name) for name in ('irw', 'mode2', 'lircd', 'ir-ctl')}
    ready = bool(lirc_devs) and (tools.get('irw') or tools.get('mode2') or tools.get('ir-ctl'))
    return {
        'ok': True,
        'ready': ready,
        'receiver': 'LIRC receiver visible' if lirc_devs else 'no /dev/lirc* receiver visible yet',
        'lirc_devices': lirc_devs,
        'gpiochips': gpiochips[:8],
        'tools': tools,
        'scan_action': 'detect GPIO/LIRC readiness only',
        'receive_action': 'bounded 8s receive with irw when configured; no transmit/replay',
        'blocked_actions': ['IR transmit/replay', 'unlock/control unknown devices', 'unbounded receive loops'],
    }


def ir_action(action: str) -> Dict[str, Any]:
    action = str(action or '').strip().lower()
    st = ir_status()
    if action in ('status', 'detect', 'scan'):
        return {'ok': True, 'action': action, 'message': 'IR readiness checked.', 'ir': st}
    if action not in ('receive-once', 'receive'):
        return {'ok': False, 'action': action, 'error': 'Supported IR actions: detect, receive-once. IR transmit/replay remains blocked until explicit owned-device wiring is approved.', 'ir': st}
    if not st.get('lirc_devices'):
        return {'ok': False, 'action': action, 'error': 'No /dev/lirc* receiver is visible yet. Configure/plug an IR receiver first.', 'ir': st}
    if not st.get('tools', {}).get('irw'):
        return {'ok': False, 'action': action, 'error': 'irw is not installed/configured. Install/configure LIRC before receiving decoded remote events.', 'ir': st}
    cp = _run(['timeout', '8', 'irw'], timeout=10)
    lines = [line.strip() for line in cp.stdout.splitlines() if line.strip()]
    if lines:
        return {'ok': True, 'action': action, 'message': f'IR receive captured {len(lines)} event(s).', 'events': lines[:12], 'ir': ir_status()}
    return {'ok': False, 'action': action, 'error': 'No decoded IR event received before the 8s timeout.', 'stdout': cp.stdout.strip()[-300:], 'stderr': cp.stderr.strip()[-300:], 'ir': ir_status()}


def nfc_rfid_action(action: str, text: str = '', owned_blank: bool = False) -> Dict[str, Any]:
    action = str(action or '').strip().lower()
    st = nfc_rfid_status()
    if action in ('status', 'detect'):
        return {'ok': True, 'action': action, 'message': 'NFC/RFID readiness checked.', 'nfc_rfid': st}
    if action not in ('read-once', 'write-owned-text'):
        return {'ok': False, 'error': 'Supported NFC/RFID actions: detect, read-once, write-owned-text with text + owned_blank=true. Clone/emulate remain gated.', 'nfc_rfid': st}
    if not st.get('ready'):
        return {'ok': False, 'error': 'MFRC522/CrowPi NFC stack is not ready yet.', 'nfc_rfid': st}
    if action == 'write-owned-text':
        payload = str(text or '').strip()
        if not owned_blank:
            return {'ok': False, 'action': action, 'error': 'Refusing write: owned_blank=true is required for an owned/blank tag.', 'nfc_rfid': st}
        if not payload:
            return {'ok': False, 'action': action, 'error': 'Refusing write: text payload is empty.', 'nfc_rfid': st}
        if len(payload) > 128:
            return {'ok': False, 'action': action, 'error': 'Refusing write: keep NFC/RFID text payload <=128 characters for this safe one-shot writer.', 'nfc_rfid': st}
        code = """
import json, os, RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
payload = os.environ.get('SPAC3_NFC_TEXT', '')
try:
    reader = SimpleMFRC522()
    reader.write(payload)
    print(json.dumps({'written_chars': len(payload)}))
finally:
    GPIO.cleanup()
"""
        env = os.environ.copy()
        env['SPAC3_NFC_TEXT'] = payload
        cp = _run(['timeout', '8', 'python3', '-c', code], timeout=10, env=env)
        if cp.returncode == 0 and cp.stdout.strip():
            return {'ok': True, 'action': action, 'message': 'NFC/RFID owned text tag write complete.', 'written_chars': len(payload), 'nfc_rfid': nfc_rfid_status()}
        return {'ok': False, 'action': action, 'error': 'No tag written before the 8s timeout, or writer returned an error.', 'stdout': cp.stdout.strip()[-300:], 'stderr': cp.stderr.strip()[-300:], 'nfc_rfid': nfc_rfid_status()}
    code = """
import json, RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
try:
    reader = SimpleMFRC522()
    uid, text = reader.read()
    print(json.dumps({'uid': str(uid), 'text': str(text).strip()}))
finally:
    GPIO.cleanup()
"""
    cp = _run(['timeout', '8', 'python3', '-c', code], timeout=10)
    if cp.returncode == 0 and cp.stdout.strip():
        try:
            data = json.loads(cp.stdout.strip().splitlines()[-1])
        except Exception:
            data = {'raw': cp.stdout.strip()[-300:]}
        return {'ok': True, 'action': action, 'message': 'NFC/RFID tag read complete.', 'tag': data, 'nfc_rfid': nfc_rfid_status()}
    return {'ok': False, 'action': action, 'error': 'No tag read before the 8s timeout, or reader returned an error.', 'stdout': cp.stdout.strip()[-300:], 'stderr': cp.stderr.strip()[-300:], 'nfc_rfid': nfc_rfid_status()}


def hardware_docks_status() -> Dict[str, Any]:
    usb = _cmd_output(['bash', '-lc', 'lsusb 2>/dev/null'], timeout=4)
    serials = sorted(str(p) for p in list(Path('/dev').glob('ttyACM*')) + list(Path('/dev').glob('ttyUSB*')))
    serial_by_id = _cmd_output(['bash', '-lc', 'ls -l /dev/serial/by-id 2>/dev/null || true'], timeout=4).splitlines()
    links = _cmd_output(['bash', '-lc', 'ip -o link 2>/dev/null | cut -d: -f2 | tr -d " "'], timeout=4).splitlines()
    lirc_devs = sorted(str(p) for p in Path('/dev').glob('lirc*'))
    gpiochips = sorted(str(p) for p in Path('/dev').glob('gpiochip*'))
    esptool = '/home/pi/.venvs/esptool/bin/esptool' if Path('/home/pi/.venvs/esptool/bin/esptool').exists() else ''
    usb_lower = usb.lower()
    esp_matches = [line for line in usb.splitlines() if any(tok in line.lower() for tok in ('303a:', '10c4:', '1a86:7523', '1a86:55d4', 'cp210', 'ch340', 'esp'))]
    rtl_sdr_matches = [line for line in usb.splitlines() if any(tok in line.lower() for tok in ('0bda:2832', '0bda:2838', 'rtl2832', 'rtl-sdr'))]
    pwn_usb = [x for x in links if x.startswith(('usb', 'enx'))]
    docks = [
        {
            'id': 'pwnagotchi-zero2', 'label': 'Pwnagotchi Pi Zero 2 WH Dock', 'kind': 'USB gadget/Ethernet/serial dock',
            'detected': bool(pwn_usb), 'candidates': pwn_usb, 'home': 'Lab → Pwnagotchi / Hashcat Workflows',
            'readiness': 'USB gadget network visible' if pwn_usb else 'plug Pwnagotchi over USB data; expect usb0/enx interface or serial console',
            'actions': ['detect', 'open workflow'], 'blocked_actions': ['auto-SSH with unknown creds', 'start deauth/capture'],
        },
        {
            'id': 'bruce-cyd', 'label': 'Bruce CYD ESP32-2432E Dock', 'kind': 'ESP32 CH340/serial dock',
            'detected': any('1a86:7523' in line for line in esp_matches), 'candidates': esp_matches, 'serials': serials,
            'home': 'Lab → Companion Firmware / Externals', 'readiness': 'CH340 serial visible; use esptool probe before flash/readback' if serials else 'plug CYD via USB data or hold BOOT/RESET if needed',
            'actions': ['detect', 'serial probe'], 'blocked_actions': ['flash without explicit firmware approval', 'RF actions outside owned lab'],
        },
        {
            'id': 'esp32-s3', 'label': 'ESP32-S3 Sense / Dev Board Dock', 'kind': 'native USB/CP210x/CH340 serial dock',
            'detected': bool(esp_matches or serials), 'candidates': esp_matches, 'serials': serials,
            'home': 'Lab → Companion Firmware', 'readiness': 'serial candidate visible; esptool installed' if serials and esptool else 'needs serial device plus esptool',
            'actions': ['detect', 'esptool chip-id'], 'blocked_actions': ['erase/flash without explicit approval'],
        },
        {
            'id': 'ir-receiver', 'label': 'IR Receiver Dock', 'kind': 'GPIO/LIRC receive',
            'detected': bool(lirc_devs or gpiochips), 'devices': lirc_devs, 'gpiochips': gpiochips[:6],
            'home': 'Lab → Safety Boundaries / Hardware', 'readiness': 'GPIO chips visible; lirc installed; configure overlay/pin for receiver' if gpiochips else 'GPIO not visible',
            'actions': ['detect', 'receive-once'], 'blocked_actions': ['transmit IR until transmitter hardware/pin confirmed'],
        },
        {
            'id': 'sdr-receiver', 'label': 'SDR Receiver Dock', 'kind': 'RTL-SDR/Soapy/433MHz receive',
            'detected': bool(rtl_sdr_matches), 'candidates': rtl_sdr_matches,
            'home': 'Signals → RF Audit / Lab → SDR', 'readiness': 'RTL-SDR visible' if rtl_sdr_matches else 'rtl-sdr/rtl_433 tools installed; plug receiver dongle to enable capture/readiness',
            'actions': ['detect', 'rtl_test receive check'], 'blocked_actions': ['transmit/jam', 'privacy-invasive decoding'],
        },
        {
            'id': 'nfc-rfid-radio', 'label': 'NFC/RFID/Radio Dock', 'kind': 'USB/SPI/I2C peripheral readiness',
            'detected': bool(nfc_rfid_status().get('ready')) or any(tok in usb_lower for tok in ('pn532','acr122','proxmark','flipper','rfid','nfc')),
            'candidates': [line for line in usb.splitlines() if any(tok in line.lower() for tok in ('pn532','acr122','proxmark','flipper','rfid','nfc'))],
            'home': 'Lab → Safety Boundaries', 'readiness': nfc_rfid_status().get('reader') if nfc_rfid_status().get('ready') else 'no NFC/RFID USB reader detected yet; GPIO/I2C wiring can be added when connected',
            'actions': ['detect'], 'blocked_actions': ['clone/write/emulate without owned tag/hardware approval'],
        },
    ]
    return {
        'ok': True,
        'usb_summary': usb.splitlines(),
        'serial_candidates': serials,
        'serial_by_id': serial_by_id,
        'esptool': esptool,
        'tools': {name: command_exists(name) for name in ('minicom', 'picocom', 'rtl_test', 'rtl_sdr', 'rtl_433', 'SoapySDRUtil', 'lircd', 'irw')},
        'docks': docks,
        'policy': 'Dock cards are readable/detectable status and bounded probes only. Flash/transmit/write/capture actions require explicit approval and owned hardware/scope.',
    }


def lab_toys_status() -> Dict[str, Any]:
    return {
        'aquarium': {
            'mode': 'local AI-style animated reef',
            'inputs': ['mood', 'weather', 'threat', 'vision', 'system load'],
            'installed': True,
            'notes': 'No external dependency; fish behavior is generated in the browser from live Spac3-Gh0st status.',
        },
        'flipper': flipper_zero_status(),
        'safety_boundaries': safety_boundary_status(),
        'workflows': lab_workflows_status(),
        'optical_audio': pi5_spdif_gpio_status(),
        'piaware': piaware_status(),
        'ir': ir_status(),
        'nfc_rfid': nfc_rfid_status(),
        'hardware_docks': hardware_docks_status(),
        'software': lab_software_status(),
    }


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
