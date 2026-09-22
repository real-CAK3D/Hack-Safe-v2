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


class MetricsTests(unittest.TestCase):
    def test_sample_has_chart_fields(self):
        from spac3ghost import metrics
        s = metrics.sample()
        for key in ('t', 'cpu', 'mem', 'disk', 'temp', 'rx', 'tx', 'load'):
            self.assertIn(key, s)

    def test_history_returns_only_new_samples(self):
        from spac3ghost import metrics
        metrics._samples.clear()
        metrics._samples.extend([{'t': 100.0}, {'t': 102.0}, {'t': 104.0}])
        h = metrics.history(since=101.0)
        self.assertEqual([x['t'] for x in h['samples']], [102.0, 104.0])
        self.assertEqual(h['interval'], metrics.INTERVAL_S)
        metrics._samples.clear()


class DeckAssetTests(unittest.TestCase):
    def test_deck_tab_is_wired_and_files_parse_as_text(self):
        from spac3ghost.paths import WEB_DIR
        html = (WEB_DIR / 'index.html').read_text(encoding='utf-8')
        for needle in ('data-tab="deck"', 'id="tab-deck"', '/deck.js', '/deck.css', '/fx.js'):
            self.assertIn(needle, html)
        for name in ('deck.js', 'deck.css', 'fx.js', 'v2.js', 'v2.css', 'weatherfx.js'):
            raw = (WEB_DIR / name).read_bytes()
            self.assertFalse(raw.startswith(b'\xef\xbb\xbf'), f'{name} has a BOM')
            text = raw.decode('utf-8')  # must be valid UTF-8
            for bad in ('\u00c2\u00b0', '\u00e2\u20ac'):  # classic mojibake for the degree sign / ellipsis
                self.assertNotIn(bad, text, f'{name} looks double-encoded')

    def test_app_js_lists_the_deck_tab(self):
        from spac3ghost.paths import WEB_DIR
        self.assertIn("'deck'", (WEB_DIR / 'app.js').read_text(encoding='utf-8'))


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


class WeatherKeyDiagnosticsTests(unittest.TestCase):
    def test_no_key_reports_configured_false_with_actionable_note(self):
        from spac3ghost.collectors import openweather_key_status
        with mock.patch('spac3ghost.collectors._openweather_key', return_value=''):
            result = openweather_key_status()
        self.assertFalse(result['configured'])
        self.assertFalse(result['valid'])
        self.assertIn('openweathermap_api_key', result['note'])

    def test_key_lookup_tolerates_quotes_and_whitespace(self):
        from spac3ghost.collectors import _openweather_key
        with mock.patch('spac3ghost.collectors.load_config', return_value={'weather': {'openweathermap_api_key': '  "abc123"  '}}):
            self.assertEqual(_openweather_key(), 'abc123')


class ConfigCorruptionRecoveryTests(unittest.TestCase):
    def test_bad_json_falls_back_without_losing_the_last_good_config(self):
        from spac3ghost import config as config_mod
        good = config_mod.load_config()
        good['weather']['openweathermap_api_key'] = 'sentinel-key'
        config_mod.save_config(good)
        config_mod._LAST_GOOD_CONFIG['value'] = None
        self.assertEqual(config_mod.load_config()['weather']['openweathermap_api_key'], 'sentinel-key')
        # _LAST_GOOD_CONFIG is now populated from the read above; that in-memory copy is the
        # safety net a corrupt file falls back to, so it must NOT be cleared before corrupting.
        original = config_mod.CONFIG_FILE.read_text(encoding='utf-8')
        try:
            config_mod.CONFIG_FILE.write_text('{not valid json', encoding='utf-8')
            recovered = config_mod.load_config()
            self.assertEqual(recovered['weather']['openweathermap_api_key'], 'sentinel-key')
            self.assertTrue(config_mod.CONFIG_FILE.with_suffix('.json.corrupt').exists())
        finally:
            config_mod.CONFIG_FILE.write_text(original, encoding='utf-8')
            config_mod.CONFIG_FILE.with_suffix('.json.corrupt').unlink(missing_ok=True)
            config_mod._LAST_GOOD_CONFIG['value'] = None


class LabToysStatusTests(unittest.TestCase):
    def test_all_sections_present_even_if_one_sub_probe_errors(self):
        from spac3ghost.controls import lab_toys_status
        with mock.patch('spac3ghost.controls.piaware_status', side_effect=RuntimeError('boom')):
            result = lab_toys_status()
        for key in ('aquarium', 'flipper', 'safety_boundaries', 'workflows', 'optical_audio',
                    'piaware', 'ir', 'nfc_rfid', 'hardware_docks', 'software'):
            self.assertIn(key, result)
        self.assertFalse(result['piaware'].get('available', True))

    def test_flipper_is_reachable_from_lab_toys_status(self):
        from spac3ghost.controls import lab_toys_status
        result = lab_toys_status()
        self.assertIn('features', result['flipper'])
        self.assertGreaterEqual(len(result['flipper']['features']), 1)


class HardwareDocksCydTests(unittest.TestCase):
    def test_cyd_buddy_dock_is_listed(self):
        from spac3ghost.controls import hardware_docks_status
        docks = hardware_docks_status()['docks']
        ids = [d['id'] for d in docks]
        self.assertIn('cyd-buddy', ids)


class CydDefaultsTests(unittest.TestCase):
    def test_defaults_match_real_firmware_behavior(self):
        from spac3ghost.cyd import DEFAULT_SETTINGS
        # Firmware backlight was always full brightness; idle-sleep was a hardcoded 30 minutes.
        self.assertEqual(DEFAULT_SETTINGS['display']['brightness'], 100)
        self.assertEqual(DEFAULT_SETTINGS['display']['sleep_s'], 1800)
        self.assertNotIn('advanced', DEFAULT_SETTINGS)  # dropped: mapped to nothing on the device

    def test_save_action_rejects_unknown_mood_and_personality(self):
        from spac3ghost.cyd import update_cyd_settings
        with mock.patch('spac3ghost.cyd.cyd_status', return_value={'connected': True}):
            result = update_cyd_settings({'action': 'save', 'values': {'face': {'mood': 'not-a-real-mood', 'personality': 'nope'}}})
        self.assertEqual(result['face']['mood'], 'auto')
        self.assertEqual(result['face']['personality'], 'sassy')


class FlipperActionTests(unittest.TestCase):
    def test_unknown_feature_is_rejected(self):
        from spac3ghost.controls import flipper_feature_action
        result = flipper_feature_action('not-a-real-feature', 'enable')
        self.assertFalse(result['ok'])


if __name__ == '__main__':
    unittest.main()
