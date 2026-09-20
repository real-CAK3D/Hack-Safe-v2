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
