import unittest

from spac3ghost.config import DEFAULT_CONFIG, load_config, save_config
from spac3ghost.personality import choose_mood, event_from_status


class SettingsMoodTests(unittest.TestCase):
    def tearDown(self):
        save_config(DEFAULT_CONFIG)

    def test_hot_threshold_is_configurable(self):
        cfg = load_config()
        cfg['mood']['hot_c'] = 50
        save_config(cfg)
        mood = choose_mood({'system': {'cpu_temp_c': 55}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {}})
        self.assertEqual(mood['name'], 'hot')

    def test_tilt_fast_event_changes_mood_and_phrase(self):
        status = {'system': {'cpu_temp_c': 40}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {'tilt_event': {'fast': True, 'orientation': 'TILTED'}}}
        self.assertEqual(choose_mood(status)['name'], 'tilted')
        self.assertEqual(event_from_status(status)['kind'], 'tilt')

    def test_level_return_event_does_not_show_tilted_mood(self):
        status = {'system': {'cpu_temp_c': 40}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {'tilt_event': {'fast': True, 'orientation': 'LEVEL'}}}
        self.assertNotEqual(choose_mood(status)['name'], 'tilted')

    def test_weather_storm_changes_mood(self):
        status = {'system': {'cpu_temp_c': 40}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {'weather': {'summary': 'Thunderstorm', 'tempF': 70}}}
        self.assertEqual(choose_mood(status)['name'], 'stormwatch')


if __name__ == '__main__':
    unittest.main()
