import unittest

from spac3ghost.config import load_config
from spac3ghost.plugins import PluginManager


class NextLevelPluginTests(unittest.TestCase):
    def test_next_level_plugins_have_config_defaults_and_load(self):
        expected = {'vpn_status', 'command_center', 'camera_watch', 'wifi_audit'}
        cfg = load_config()
        self.assertTrue(expected.issubset(set(cfg.get('plugins', {}))))
        manager = PluginManager()
        manager.load()
        loaded = {p['name'] for p in manager.describe() if p.get('loaded')}
        self.assertTrue(expected.issubset(loaded))


if __name__ == '__main__':
    unittest.main()
