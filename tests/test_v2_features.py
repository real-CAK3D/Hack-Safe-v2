import unittest
from unittest import mock

from spac3ghost import hostinfo, __version__
from spac3ghost.collectors import service_status, system_status


class HostInfoTests(unittest.TestCase):
    def test_uptime_is_positive_int(self):
        self.assertIsInstance(hostinfo.uptime_s(), int)
        self.assertGreaterEqual(hostinfo.uptime_s(), 0)

    def test_disks_have_dashboard_shape(self):
        rows = hostinfo.disks()
        self.assertTrue(rows)
        for key in ('filesystem', 'size', 'used', 'avail', 'use_percent', 'mount'):
            self.assertIn(key, rows[0])
        self.assertTrue(rows[0]['use_percent'].endswith('%'))

    def test_system_status_never_raises_and_has_core_fields(self):
        data = system_status()
        for key in ('hostname', 'uptime_s', 'memory', 'cpu_live', 'disk_root', 'disk_all', 'ips'):
            self.assertIn(key, data)
        self.assertIsInstance(data['uptime_s'], int)

    def test_platform_summary(self):
        info = hostinfo.platform_summary()
        self.assertTrue(info['os'])
        self.assertGreaterEqual(info['cpus'], 1)


class ServiceStatusTests(unittest.TestCase):
    def test_no_systemd_means_no_fake_offline_services(self):
        with mock.patch('spac3ghost.collectors.shutil.which', return_value=None), \
             mock.patch('spac3ghost.collectors._MEM_CACHE', {}):
            self.assertEqual({k: v for k, v in service_status().items() if k != 'cached'}, {})


class HealthEndpointTests(unittest.TestCase):
    def test_health_payload_shape(self):
        from spac3ghost.app import health_payload
        payload = health_payload()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['version'], __version__)
        self.assertEqual(set(payload['plugins']), {'loaded', 'enabled', 'total'})


class RequestGuardTests(unittest.TestCase):
    def test_same_origin_and_plain_requests_are_allowed(self):
        from spac3ghost.app import check_request
        self.assertIsNone(check_request({'Host': '127.0.0.1:8765'}, 'POST'))
        self.assertIsNone(check_request({'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765'}, 'POST'))
        self.assertIsNone(check_request({'Host': 'hack-safe.tail1234.ts.net:8765'}, 'GET'))
        self.assertIsNone(check_request({'Host': '100.64.0.5:8765'}, 'GET'))

    def test_cross_site_and_rebinding_are_refused(self):
        from spac3ghost.app import check_request
        self.assertTrue(check_request({'Host': '127.0.0.1:8765', 'Origin': 'http://evil.example'}, 'POST'))
        self.assertTrue(check_request({'Host': '127.0.0.1:8765', 'Origin': 'null'}, 'POST'))
        self.assertTrue(check_request({'Host': '127.0.0.1:8765', 'Sec-Fetch-Site': 'cross-site'}, 'GET'))
        self.assertTrue(check_request({'Host': 'attacker.example.com:8765'}, 'GET'))
        self.assertTrue(check_request({}, 'GET'))


class ControlsRobustnessTests(unittest.TestCase):
    def test_run_reports_missing_tools_instead_of_raising(self):
        from spac3ghost.controls import _run
        cp = _run(['definitely-not-a-real-binary-xyz'])
        self.assertEqual(cp.returncode, 127)

    def test_action_endpoints_survive_unknown_ids(self):
        from spac3ghost.controls import lab_software_action, spicy_tool_action
        self.assertFalse(spicy_tool_action('nope', 'bogus')['ok'])
        self.assertFalse(lab_software_action('nope', 'bogus')['ok'])

    def test_service_watchdog_ignores_cache_flag(self):
        import importlib.util
        from spac3ghost.paths import PLUGIN_DIR
        spec = importlib.util.spec_from_file_location('wd', PLUGIN_DIR / 'service_watchdog.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = mod.Plugin().on_status({'services': {'ssh': {'active': True}, 'gpsd': {'active': False}, 'cached': True}})
        self.assertEqual(out['lines'], ['DOWN: gpsd'])


class ProtonMapTests(unittest.TestCase):
    """Guards the marker anchors that keep pins on land."""

    def _app_js(self):
        from spac3ghost.paths import WEB_DIR
        return (WEB_DIR / 'app.js').read_text(encoding='utf-8')

    def test_every_marker_has_an_anchor_inside_the_map(self):
        import re
        js = self._app_js()
        block = js[js.index('const MAP_ANCHORS={'):js.index('function mapAnchorPercent')]
        anchors = {m.group(1): (int(m.group(2)), int(m.group(3))) for m in re.finditer(r"'([A-Z-]+)':\[(\d+),(\d+)\]", block)}
        markers = set(re.findall(r"\{name:'([A-Z-]+)',x:", js))
        self.assertGreaterEqual(len(markers), 20)
        self.assertEqual(markers - set(anchors), set(), 'markers without a verified anchor')
        for name, (x, y) in anchors.items():
            self.assertTrue(0 < x < 1538.434 and 0 < y < 700, f'{name} anchor is outside the SVG')

    def test_anchors_are_normalised_against_the_svg_size(self):
        js = self._app_js()
        self.assertIn('PROTON_MAP_W=1538.434', js)
        self.assertIn('proton-map-canvas', js)


class WeatherFxTests(unittest.TestCase):
    def test_engine_ships_and_is_loaded(self):
        from spac3ghost.paths import WEB_DIR
        js = (WEB_DIR / 'weatherfx.js').read_text(encoding='utf-8')
        for word in ('drawRain', 'drawSnow', 'drawLightning', 'moonPhase', 'drawFog'):
            self.assertIn(word, js)
        self.assertIn('/weatherfx.js', (WEB_DIR / 'index.html').read_text(encoding='utf-8'))


class FrontendAssetTests(unittest.TestCase):
    def test_v2_assets_are_wired_into_index(self):
        from spac3ghost.paths import WEB_DIR
        html = (WEB_DIR / 'index.html').read_text(encoding='utf-8')
        self.assertIn('/v2.css', html)
        self.assertIn('/v2.js', html)
        self.assertTrue((WEB_DIR / 'v2.css').exists())
        self.assertTrue((WEB_DIR / 'v2.js').exists())


if __name__ == '__main__':
    unittest.main()
