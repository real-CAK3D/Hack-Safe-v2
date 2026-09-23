import unittest
from unittest import mock

from spac3ghost import pwnagotchi_dock as pd


def _reset_cache():
    with pd._STATE_LOCK:
        pd._STATE = {}
        pd._STATE_AT = 0.0
        pd._REFRESHING = False


SAMPLE_HTML = """
<html><body>
  <span id="name">CAK3DAGOTCHI</span>
  <span id="status">AUTO</span>
  <span id="channel">6</span>
  <span id="aps">42</span>
  <span id="uptime">03:14:15</span>
  <span id="shakes">7</span>
</body></html>
"""


class ParseStatsTests(unittest.TestCase):
    def test_parses_known_spans(self):
        stats = pd._parse_stats(SAMPLE_HTML)
        self.assertEqual(stats['name'], 'CAK3DAGOTCHI')
        self.assertEqual(stats['aps'], '42')
        self.assertEqual(stats['shakes'], '7')
        self.assertEqual(stats['uptime'], '03:14:15')

    def test_missing_spans_are_absent_not_errors(self):
        self.assertEqual(pd._parse_stats('<html>nothing here</html>'), {})


class ConfigResolutionTests(unittest.TestCase):
    def test_env_host_overrides_and_splits(self):
        with mock.patch.dict('os.environ', {'SPAC3GHOST_PWN_HOST': '1.2.3.4, 5.6.7.8'}, clear=False):
            self.assertEqual(pd._hosts(), ['1.2.3.4', '5.6.7.8'])

    def test_creds_prefer_env(self):
        with mock.patch.dict('os.environ', {'SPAC3GHOST_PWN_USER': 'pi', 'SPAC3GHOST_PWN_PASS': 'secret'}, clear=False):
            self.assertEqual(pd._creds(), ('pi', 'secret'))

    def test_creds_fall_back_to_stock_default(self):
        with mock.patch.object(pd, '_cfg', return_value={}), \
             mock.patch.dict('os.environ', {}, clear=True):
            self.assertEqual(pd._creds(), (pd.DEFAULT_USER, pd.DEFAULT_PASS))


class ProbeTests(unittest.TestCase):
    def setUp(self):
        _reset_cache()

    def test_first_reachable_host_wins_and_stats_parsed(self):
        calls = []

        def fake_open(host, path, timeout):
            calls.append(host)
            if host == 'good-host':
                return 200, SAMPLE_HTML.encode('utf-8'), 'text/html'
            raise OSError('no route to host')

        with mock.patch.object(pd, '_hosts', return_value=['dead-host', 'good-host']), \
             mock.patch.object(pd, '_open', side_effect=fake_open):
            snap = pd._probe()

        self.assertTrue(snap['reachable'])
        self.assertTrue(snap['authed'])
        self.assertEqual(snap['host'], 'good-host')
        self.assertEqual(snap['networks_seen'], '42')
        self.assertEqual(snap['handshakes'], '7')
        self.assertEqual(snap['face_proxy'], '/api/pwnagotchi/ui')
        self.assertIn('dead-host', calls)

    def test_reachable_but_401_is_online_not_authed(self):
        with mock.patch.object(pd, '_hosts', return_value=['locked-host']), \
             mock.patch.object(pd, '_open', return_value=(401, b'nope', 'text/html')):
            snap = pd._probe()
        self.assertTrue(snap['reachable'])
        self.assertFalse(snap['authed'])
        self.assertIn('LOGIN', snap['dock_label'])

    def test_all_hosts_down_is_offline(self):
        with mock.patch.object(pd, '_hosts', return_value=['a', 'b']), \
             mock.patch.object(pd, '_open', side_effect=OSError('down')):
            snap = pd._probe()
        self.assertFalse(snap['reachable'])
        self.assertEqual(snap['dock_label'], 'OFFLINE')


class StatusCacheTests(unittest.TestCase):
    def setUp(self):
        _reset_cache()

    def test_first_call_returns_probing_stub_without_blocking(self):
        with mock.patch.object(pd.threading, 'Thread') as thread:
            out = pd.pwn_dock_status()
        self.assertEqual(out['dock_label'], 'PROBING')
        self.assertTrue(thread.called)  # a background refresh was scheduled

    def test_fresh_cache_is_returned_without_new_probe(self):
        with pd._STATE_LOCK:
            pd._STATE = {'ok': True, 'reachable': True, 'dock_label': 'ONLINE', 'host': 'x'}
            pd._STATE_AT = pd.time.time()
        with mock.patch.object(pd.threading, 'Thread') as thread:
            out = pd.pwn_dock_status()
        self.assertEqual(out['dock_label'], 'ONLINE')
        self.assertFalse(thread.called)


class FaceProxyTests(unittest.TestCase):
    def setUp(self):
        _reset_cache()

    def test_returns_png_from_working_host(self):
        with mock.patch.object(pd, '_hosts', return_value=['h1']), \
             mock.patch.object(pd, '_open', return_value=(200, b'\x89PNG...', 'image/png')):
            body, ctype, code = pd.fetch_ui_png()
        self.assertEqual(code, 200)
        self.assertEqual(ctype, 'image/png')
        self.assertTrue(body.startswith(b'\x89PNG'))

    def test_reports_failure_when_no_host_serves_face(self):
        with mock.patch.object(pd, '_hosts', return_value=['h1']), \
             mock.patch.object(pd, '_open', return_value=(401, b'', 'text/html')):
            body, ctype, code = pd.fetch_ui_png()
        self.assertIsNone(body)
        self.assertEqual(code, 401)


class HardwareDockIntegrationTests(unittest.TestCase):
    def test_pwnagotchi_dock_reflects_web_reachability(self):
        from spac3ghost.controls import hardware_docks_status
        online = {'reachable': True, 'host': '100.100.63.24', 'dock_label': 'ONLINE'}
        with mock.patch('spac3ghost.pwnagotchi_dock.pwn_dock_status', return_value=online):
            docks = hardware_docks_status()['docks']
        dock = next(d for d in docks if d['id'] == 'pwnagotchi-zero2')
        self.assertTrue(dock['detected'])
        self.assertIn('100.100.63.24', dock['candidates'])


if __name__ == '__main__':
    unittest.main()
