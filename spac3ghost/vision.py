from __future__ import annotations

import time
from pathlib import Path
import json
from threading import Lock
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen

from .config import load_config
from .paths import DATA_DIR, HOME, ROOT

MODEL_PATHS = [(HOME / 'yolov8n.pt'), (ROOT / 'models/yolov8n.pt')]
DEFAULT_DEVICE = '/dev/video0'
VISION_HISTORY_FILE = DATA_DIR / 'vision_history.json'
SNAP_DIR = DATA_DIR / 'vision_snaps'
_MODEL = None
_MODEL_ERROR = ''
_MODEL_LOCK = Lock()
_CAPTURE_LOCK = Lock()
_LAST_ANALYSIS: Dict[str, Any] = {'ts': 0, 'detections': [], 'error': ''}
_LAST_JPEG: bytes = b''
_LAST_JPEGS: Dict[str, bytes] = {}
_LOCAL_CAPTURE = None
_LOCAL_CAPTURE_KEY = ''
_LOCAL_CAPTURE_TS = 0.0

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 15
DEFAULT_JPEG_QUALITY = 90


def configured_feeds(cfg: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    cfg = cfg or load_config().get('vision', {})
    feeds = cfg.get('feeds') if isinstance(cfg.get('feeds'), list) else []
    normalized: List[Dict[str, Any]] = []
    for item in feeds:
        if not isinstance(item, dict):
            continue
        feed_id = str(item.get('id') or item.get('name') or '').strip().lower().replace(' ', '-')
        if not feed_id:
            continue
        feed = dict(item)
        feed['id'] = feed_id
        feed['label'] = str(item.get('label') or feed_id)
        feed['source'] = str(item.get('source') or 'url').lower()
        normalized.append(feed)
    if not any(f.get('id') == 'local' for f in normalized):
        normalized.insert(0, {'id': 'local', 'label': 'Hack-Safe Cam', 'source': 'usb', 'device': cfg.get('device') or DEFAULT_DEVICE})
    if not any(f.get('id') == 'bak3ry' for f in normalized):
        normalized.append({'id': 'bak3ry', 'label': 'theBAK3RY Cam', 'source': 'url', 'snapshot_url': str(cfg.get('bak3ry_snapshot_url') or cfg.get('bak3ry_stream_url') or '').strip()})
    if not any(f.get('id') == 'jeffeybot' for f in normalized):
        normalized.append({'id': 'jeffeybot', 'label': 'Jeffeybot Car Cam', 'source': 'url', 'snapshot_url': str(cfg.get('jeffeybot_snapshot_url') or 'http://192.168.18.42:9000/mjpg').strip()})
    return normalized


def select_feed(cfg: Dict[str, Any] | None = None, feed_id: str | None = None) -> Dict[str, Any]:
    cfg = cfg or load_config().get('vision', {})
    feeds = configured_feeds(cfg)
    selected = str(feed_id or cfg.get('selected_feed') or cfg.get('active_feed') or 'local').strip().lower()
    return next((f for f in feeds if f.get('id') == selected), feeds[0])


def _cv2():
    import cv2  # type: ignore
    return cv2


def _np():
    import numpy as np  # type: ignore
    return np



def _vision_history_rows():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if VISION_HISTORY_FILE.exists():
            return json.loads(VISION_HISTORY_FILE.read_text())
    except Exception:
        pass
    return []


def vision_history(limit: int = 20) -> Dict[str, Any]:
    rows = _vision_history_rows()[-limit:]
    return {'available': True, 'items': list(reversed(rows)), 'count': len(_vision_history_rows())}




def clear_vision_history() -> Dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    removed_files = 0
    removed_rows = 0
    try:
        rows = _vision_history_rows()
        removed_rows = len(rows) if isinstance(rows, list) else 0
    except Exception:
        removed_rows = 0
    if VISION_HISTORY_FILE.exists():
        try:
            VISION_HISTORY_FILE.unlink()
        except Exception:
            VISION_HISTORY_FILE.write_text('[]')
    if SNAP_DIR.exists():
        for snap in SNAP_DIR.glob('*.jpg'):
            try:
                snap.unlink()
                removed_files += 1
            except Exception:
                pass
    return {'ok': True, 'available': True, 'removed_rows': removed_rows, 'removed_snapshots': removed_files, 'items': [], 'count': 0}

def _save_vision_history(entry: Dict[str, Any], jpeg: bytes | None = None) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = _vision_history_rows()
    ts = int(entry.get('ts') or time.time())
    if jpeg:
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        snap = SNAP_DIR / f'{ts}.jpg'
        try:
            snap.write_bytes(jpeg)
            entry['snapshot'] = f'/api/camera/snapshot/{snap.name}'
        except Exception:
            pass
    rows.append(entry)
    rows = rows[-80:]
    VISION_HISTORY_FILE.write_text(json.dumps(rows, indent=2, sort_keys=True))


def available_yolo_model() -> str:
    for path in MODEL_PATHS:
        if path.exists():
            return str(path)
    return ''


def vision_backend_status() -> Dict[str, Any]:
    # Lightweight status check only. Importing ultralytics on every dashboard refresh
    # is expensive on the Pi; the real import/model load happens only when YOLO scan runs.
    model = available_yolo_model()
    return {
        'available': bool(model),
        'backend': 'yolo' if model else 'not_configured',
        'model': model,
        'ultralytics': 'not probed on refresh',
        'error': '' if model else 'No YOLO model file found.',
    }


def _load_model():
    global _MODEL, _MODEL_ERROR
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        model_path = available_yolo_model()
        if not model_path:
            _MODEL_ERROR = 'No YOLO model file found.'
            return None
        try:
            from ultralytics import YOLO  # type: ignore
            _MODEL = YOLO(model_path)
            _MODEL_ERROR = ''
            return _MODEL
        except Exception as exc:
            _MODEL_ERROR = str(exc)
            return None


def _camera_setting(cfg: Dict[str, Any], name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(cfg.get(name, default))
    except Exception:
        value = default
    return max(lo, min(hi, value))


def _open_local_capture(device: str, cfg: Dict[str, Any]):
    global _LOCAL_CAPTURE, _LOCAL_CAPTURE_KEY, _LOCAL_CAPTURE_TS
    cv2 = _cv2()
    width = _camera_setting(cfg, 'width', DEFAULT_WIDTH, 320, 1920)
    height = _camera_setting(cfg, 'height', DEFAULT_HEIGHT, 240, 1080)
    fps = _camera_setting(cfg, 'fps', DEFAULT_FPS, 5, 30)
    key = f'{device}:{width}x{height}@{fps}'
    if _LOCAL_CAPTURE is not None and _LOCAL_CAPTURE_KEY == key and _LOCAL_CAPTURE.isOpened():
        _LOCAL_CAPTURE_TS = time.time()
        return _LOCAL_CAPTURE
    if _LOCAL_CAPTURE is not None:
        try:
            _LOCAL_CAPTURE.release()
        except Exception:
            pass
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        _LOCAL_CAPTURE = None
        _LOCAL_CAPTURE_KEY = ''
        return None
    # Ask the camera for MJPEG at 720p-ish. Many cheap USB webcams look muddy or
    # stutter if left at the driver's tiny default YUYV mode.
    try:
        fourcc = getattr(cv2, 'VideoWriter_fourcc', None)
        if fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    _LOCAL_CAPTURE = cap
    _LOCAL_CAPTURE_KEY = key
    _LOCAL_CAPTURE_TS = time.time()
    return cap


def _release_stale_local_capture(max_idle_s: float = 20.0) -> None:
    global _LOCAL_CAPTURE, _LOCAL_CAPTURE_KEY
    if _LOCAL_CAPTURE is not None and time.time() - _LOCAL_CAPTURE_TS > max_idle_s:
        try:
            _LOCAL_CAPTURE.release()
        except Exception:
            pass
        _LOCAL_CAPTURE = None
        _LOCAL_CAPTURE_KEY = ''


def capture_frame(device: str = DEFAULT_DEVICE, cfg: Dict[str, Any] | None = None):
    global _LOCAL_CAPTURE, _LOCAL_CAPTURE_KEY
    cfg = cfg or {}
    if not _CAPTURE_LOCK.acquire(timeout=1.5):
        return None, f'{device} is busy'
    try:
        cap = _open_local_capture(device, cfg)
        if cap is None:
            return None, f'{device} did not open'
        frame = None
        ok = False
        # Drain stale buffered frames before reading the one we show. This makes
        # the dashboard feel live instead of showing a half-second-old queue.
        for _ in range(2):
            try:
                cap.grab()
            except Exception:
                break
        for _ in range(3):
            ok, frame = cap.read()
            if ok and frame is not None:
                break
        if not ok or frame is None:
            try:
                cap.release()
            except Exception:
                pass
            _LOCAL_CAPTURE = None
            _LOCAL_CAPTURE_KEY = ''
            return None, f'{device} did not return a frame'
        return frame, ''
    finally:
        _release_stale_local_capture()
        _CAPTURE_LOCK.release()


def capture_url_frame(url: str, timeout_s: float = 4.0):
    cv2 = _cv2()
    np = _np()
    if not url:
        return None, 'Remote camera URL is not configured.'
    if not _CAPTURE_LOCK.acquire(timeout=2.0):
        return None, f'{url} is busy'
    try:
        req = Request(url, headers={'User-Agent': 'Spac3-Gh0st/0.2'})
        with urlopen(req, timeout=timeout_s) as resp:
            ctype = (resp.headers.get('content-type') or '').lower()
            if 'multipart/x-mixed-replace' in ctype or 'mjpg' in url.lower() or 'mjpeg' in url.lower():
                data = b''
                deadline = time.time() + timeout_s
                while len(data) < 512_000 and time.time() < deadline:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    data += chunk
                    frame_start = data.find(bytes([0xff, 0xd8]))
                    frame_end = data.find(bytes([0xff, 0xd9]), frame_start + 2) if frame_start >= 0 else -1
                    if frame_start >= 0 and frame_end > frame_start:
                        data = data[frame_start:frame_end + 2]
                        break
            else:
                data = resp.read(2_000_000)
        # Snapshot URLs return a JPEG directly. MJPEG streams return multipart bytes;
        # pull the first JPEG frame out so SunFounder/car camera streams can be used
        # as Vision feeds without a separate proxy.
        frame_start = data.find(bytes([0xff, 0xd8]))
        frame_end = data.find(bytes([0xff, 0xd9]), frame_start + 2) if frame_start >= 0 else -1
        if frame_start >= 0 and frame_end > frame_start:
            data = data[frame_start:frame_end + 2]
        arr = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None, f'{url} did not return a decodable JPEG frame'
        return frame, ''
    except Exception as exc:
        return None, f'{url} failed: {exc}'
    finally:
        _CAPTURE_LOCK.release()

def capture_configured_frame(cfg: Dict[str, Any], feed_id: str | None = None):
    feed = select_feed(cfg, feed_id)
    source = str(feed.get('source') or cfg.get('source') or '').lower()
    url = str(feed.get('stream_url') or feed.get('snapshot_url') or cfg.get('stream_url') or cfg.get('snapshot_url') or '').strip()
    if source in ('esp32', 'url', 'remote') or url:
        return capture_url_frame(url)
    merged_cfg = {**cfg, **feed}
    return capture_frame(str(feed.get('device') or cfg.get('device') or DEFAULT_DEVICE), merged_cfg)


def _placeholder(message: str):
    cv2 = _cv2()
    np = _np()
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    img[:] = (5, 8, 8)
    cv2.putText(img, 'SPAC3-GH0ST VISION', (28, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (80, 255, 120), 2)
    y = 135
    for part in [message[i:i+46] for i in range(0, len(message), 46)][:5]:
        cv2.putText(img, part, (28, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (190, 255, 205), 1)
        y += 34
    return img


def _draw_detections(frame, detections: List[Dict[str, Any]]):
    cv2 = _cv2()
    h, w = frame.shape[:2]
    thickness = max(2, round(min(w, h) / 360))
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det.get('xyxy', [0, 0, 0, 0])]
        label = f"{det.get('label', 'object')} {det.get('confidence', 0):.2f}"
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (39, 255, 96), thickness)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.62, thickness)
        label_y = max(th + 10, y1 - 8)
        cv2.rectangle(frame, (x1, label_y - th - 8), (min(w - 1, x1 + tw + 10), label_y + 4), (0, 0, 0), -1)
        cv2.putText(frame, label, (x1 + 5, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (185, 255, 200), thickness, cv2.LINE_AA)
    cv2.putText(frame, time.strftime('VISION %H:%M:%S'), (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (90, 220, 255), 2, cv2.LINE_AA)
    return frame


def analyze_current_frame(conf: float = 0.25, imgsz: int = 320, feed_id: str | None = None) -> Dict[str, Any]:
    global _LAST_ANALYSIS
    cfg = load_config().get('vision', {})
    feed = select_feed(cfg, feed_id)
    feed_key = str(feed.get('id') or 'local')
    if not cfg.get('enabled'):
        _LAST_ANALYSIS = {'ts': int(time.time()), 'detections': [], 'error': 'Vision is off.'}
        return {'ok': False, **vision_backend_status(), 'feed': feed_key, **_LAST_ANALYSIS}
    frame, error = capture_configured_frame(cfg, feed_key)
    if error:
        _LAST_ANALYSIS = {'ts': int(time.time()), 'detections': [], 'error': error}
        return {'ok': False, **vision_backend_status(), 'feed': feed_key, **_LAST_ANALYSIS}
    assert frame is not None
    model = _load_model()
    if model is None:
        _LAST_ANALYSIS = {'ts': int(time.time()), 'detections': [], 'error': _MODEL_ERROR or 'YOLO model unavailable.'}
        return {'ok': False, **vision_backend_status(), 'feed': feed_key, **_LAST_ANALYSIS}
    started = time.time()
    results = model.predict(frame, imgsz=imgsz, conf=conf, verbose=False, device='cpu')
    detections: List[Dict[str, Any]] = []
    if results and getattr(results[0], 'boxes', None) is not None:
        names = results[0].names
        for box in results[0].boxes[:12]:
            cls = int(box.cls[0])
            detections.append({
                'label': names.get(cls, str(cls)) if isinstance(names, dict) else str(cls),
                'confidence': round(float(box.conf[0]), 3),
                'xyxy': [round(float(v), 1) for v in box.xyxy[0].tolist()],
            })
    _LAST_ANALYSIS = {'ts': int(time.time()), 'detections': detections, 'error': '', 'elapsed_s': round(time.time() - started, 2)}
    try:
        jpg_quality = _camera_setting(cfg, 'jpeg_quality', DEFAULT_JPEG_QUALITY, 65, 95)
        ok, buf = _cv2().imencode('.jpg', _draw_detections(frame.copy(), detections), [int(_cv2().IMWRITE_JPEG_QUALITY), jpg_quality])
        labels = [d.get('label', 'object') for d in detections]
        _save_vision_history({'ts': _LAST_ANALYSIS['ts'], 'ok': True, 'feed': str(feed.get('id') or 'local'), 'labels': labels[:8], 'detections': detections[:8], 'elapsed_s': _LAST_ANALYSIS['elapsed_s']}, buf.tobytes() if ok else None)
    except Exception:
        _save_vision_history({'ts': _LAST_ANALYSIS['ts'], 'ok': True, 'feed': str(feed.get('id') or 'local'), 'labels': [d.get('label', 'object') for d in detections[:8]], 'detections': detections[:8], 'elapsed_s': _LAST_ANALYSIS['elapsed_s']})
    return {'ok': True, 'feed': str(feed.get('id') or 'local'), **_LAST_ANALYSIS, **vision_backend_status()}


def last_analysis() -> Dict[str, Any]:
    return dict(_LAST_ANALYSIS)


def _svg_placeholder(message: str) -> Tuple[bytes, str]:
    """Dependency-free placeholder used when OpenCV/numpy are not installed."""
    from html import escape
    lines = [message[i:i + 46] for i in range(0, len(message), 46)][:5]
    text = ''.join(f'<text x="28" y="{135 + 34 * n}" fill="#bfffcd" font-size="20">{escape(part)}</text>' for n, part in enumerate(lines))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360" font-family="monospace">'
        '<rect width="640" height="360" fill="#050808"/>'
        '<text x="28" y="70" fill="#50ff78" font-size="30" font-weight="bold">SPAC3-GH0ST VISION</text>'
        f'{text}</svg>'
    )
    return svg.encode('utf-8'), 'image/svg+xml'


def jpeg_frame(with_detections: bool = True, feed_id: str | None = None) -> Tuple[bytes, str]:
    global _LAST_JPEG
    cfg = load_config().get('vision', {})
    try:
        cv2 = _cv2()
        _np()
    except ImportError:
        why = 'Vision is OFF.' if not cfg.get('enabled') else 'Camera needs OpenCV.'
        return _svg_placeholder(f'{why} Install optional deps: pip install -r requirements-vision.txt')
    feed = select_feed(cfg, feed_id)
    key = str(feed.get('id') or 'local')
    if not cfg.get('enabled'):
        frame = _placeholder('Vision is OFF. Hit Arm Vision to enable the camera feed.')
    else:
        frame, error = capture_configured_frame(cfg, key)
        if error:
            # Keep feed truth intact: do not borrow a stale JPEG from another camera.
            # Remote/cross-feed fallback made Jeffeybot look live when its PiCar-X
            # endpoint was actually down/refused.
            cached = _LAST_JPEGS.get(key)
            if cached:
                return cached, 'image/jpeg'
            frame = _placeholder(f"{feed.get('label', key)}: {error}")
        elif with_detections:
            assert frame is not None
            frame = _draw_detections(frame, list(_LAST_ANALYSIS.get('detections') or []))
    assert frame is not None
    jpg_quality = _camera_setting(cfg, 'jpeg_quality', DEFAULT_JPEG_QUALITY, 65, 95)
    ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpg_quality])
    if not ok:
        raise RuntimeError('Could not encode camera frame.')
    _LAST_JPEG = buf.tobytes()
    _LAST_JPEGS[key] = _LAST_JPEG
    return _LAST_JPEG, 'image/jpeg'
