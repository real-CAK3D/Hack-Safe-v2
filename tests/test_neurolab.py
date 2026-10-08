import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from spac3ghost import neurolab

SUMMARY = {'ok': True, 'tick': 7, 'facility': {'employees': 12, 'tasks': {'open': 4}}, 'services': [], 'telemetry': {'online': 2, 'total': 6}}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/api/summary':
            self.send_response(404); self.end_headers(); return
        body = json.dumps(SUMMARY).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(body)

    def log_message(self, *args):
        pass


def _serve():
    server = HTTPServer(('127.0.0.1', 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _reset():
    neurolab._CACHE.update(at=0.0, url='', value=None, last_good=None, last_good_at=0.0)


def test_neurolab_status_reads_summary(monkeypatch):
    server = _serve()
    try:
        _reset()
        monkeypatch.setenv('SPAC3GHOST_NEUROLAB_URL', f'http://127.0.0.1:{server.server_port}/')
        out = neurolab.neurolab_status(force=True)
        assert out['available'] is True and out['stale'] is False
        assert out['summary']['tick'] == 7 and out['summary']['latency_ms'] >= 0
        assert out['url'] == f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()


def test_neurolab_status_serves_stale_then_offline(monkeypatch):
    server = _serve()
    _reset()
    monkeypatch.setenv('SPAC3GHOST_NEUROLAB_URL', f'http://127.0.0.1:{server.server_port}')
    assert neurolab.neurolab_status(force=True)['available'] is True
    server.shutdown(); server.server_close()
    out = neurolab.neurolab_status(force=True)
    assert out['available'] is True and out['stale'] is True and out['error']
    _reset()
    out = neurolab.neurolab_status(force=True)
    assert out['available'] is False and out['error']


def test_neurolab_status_can_be_disabled(monkeypatch):
    _reset()
    monkeypatch.setattr(neurolab, 'load_config', lambda: {'neurolab': {'enabled': False}})
    assert neurolab.neurolab_status(force=True) == {'available': False, 'enabled': False, 'error': 'disabled in config'}


def test_neurolab_role_strings():
    snap = {'available': True, 'stale': False, 'summary': {'tick': 389, 'services': [{'ok': True}] * 4, 'telemetry': {'online': 2, 'total': 6}}}
    assert neurolab.neurolab_role(snap) == 'facility telemetry sim // online · tick 389 · 4/4 services · telemetry 2/6'
    assert neurolab.neurolab_role({**snap, 'stale': True}).endswith('stale · tick 389 · 4/4 services · telemetry 2/6')
    assert neurolab.neurolab_role({'available': False}).endswith('offline')
    assert neurolab.neurolab_state({'available': False}) == 'offline'


def test_household_signals_lists_neurolab_after_ruview(monkeypatch):
    from spac3ghost import collectors
    monkeypatch.setattr(neurolab, 'neurolab_snapshot', lambda: {'available': False, 'url': 'https://nl.example', 'error': 'x'})
    out = collectors.household_signals_status({'known_devices': {'devices': []}})
    ids = [s['id'] for s in out['services']]
    assert ids[-2:] == ['ruview', 'neurolab']
    nl = out['services'][-1]
    assert nl['url'] == 'https://nl.example' and nl['role'].endswith('offline') and nl['label'] == 'NeuroLab @ NukeBox'


def test_household_signals_survives_neurolab_failure(monkeypatch):
    from spac3ghost import collectors
    def boom():
        raise RuntimeError('nope')
    monkeypatch.setattr(neurolab, 'neurolab_snapshot', boom)
    out = collectors.household_signals_status({'known_devices': {'devices': []}})
    assert [s['id'] for s in out['services']][-1] == 'ruview'
