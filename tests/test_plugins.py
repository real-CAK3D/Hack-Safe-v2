import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from spac3ghost.config import DEFAULT_CONFIG, load_config, save_config
from spac3ghost.plugins import PluginManager


class PluginManagerTests(unittest.TestCase):
    def setUp(self):
        self._original_config = deepcopy(load_config())

    def tearDown(self):
        save_config(self._original_config)

    def test_disabled_plugin_is_not_loaded(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'ghost_logger.py'
            path.write_text("class Plugin:\n    name='ghost_logger'\n")
            cfg = DEFAULT_CONFIG.copy()
            cfg['plugins'] = dict(DEFAULT_CONFIG['plugins'])
            cfg['plugins']['ghost_logger'] = False
            save_config(cfg)
            manager = PluginManager(Path(d))
            manager.load()
            self.assertEqual(manager.plugins, [])
            self.assertFalse(manager.describe()[0]['enabled'])


if __name__ == '__main__':
    unittest.main()
