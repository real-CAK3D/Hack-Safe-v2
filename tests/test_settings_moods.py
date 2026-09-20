import unittest
from copy import deepcopy

from spac3ghost.config import DEFAULT_CONFIG, load_config, save_config
from spac3ghost.personality import choose_mood, event_from_status


class SettingsMoodTests(unittest.TestCase):
    def setUp(self):
        self._original_config = deepcopy(load_config())

    def tearDown(self):
        save_config(self._original_config)

    def test_hot_threshold_is_configurable(self):
        cfg = load_config()
        cfg['mood']['hot_c'] = 50
        save_config(cfg)
        mood = choose_mood({'system': {'cpu_temp_c': 55}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {}})
        self.assertEqual(mood['name'], 'hot')

    def test_tilt_fast_event_changes_phrase_but_not_primary_face_mood(self):
        status = {'system': {'cpu_temp_c': 40}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {'tilt_event': {'fast': True, 'orientation': 'TILTED'}}}
        # The face/mood should remain time/weather oriented; movement is reflected in the phrase/event.
        self.assertNotEqual(choose_mood(status)['name'], 'tilted')
        self.assertEqual(event_from_status(status)['kind'], 'movement')

    def test_level_return_event_does_not_show_tilted_mood(self):
        status = {'system': {'cpu_temp_c': 40}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {'tilt_event': {'fast': True, 'orientation': 'LEVEL'}}}
        self.assertNotEqual(choose_mood(status)['name'], 'tilted')

    def test_weather_storm_sometimes_flavors_mood_without_dominating(self):
        status = {'system': {'cpu_temp_c': 40}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {'weather': {'summary': 'Thunderstorm', 'tempF': 70}}}
        names = {choose_mood(status, now=ts)['name'] for ts in range(0, 900, 31)}
        self.assertIn('stormwatch', names)
        self.assertTrue(names & {'morning', 'daylight', 'evening', 'night', 'curious'})

    def test_rain_flavors_face_sequence_with_normal_moods(self):
        status = {'system': {'cpu_temp_c': 40}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {'weather': {'summary': 'Rain showers', 'tempF': 70}}}
        names = [choose_mood(status, now=ts)['name'] for ts in range(0, 1200, 29)]
        self.assertIn('rainwatch', names)
        self.assertGreater(sum(name != 'rainwatch' for name in names), sum(name == 'rainwatch' for name in names))


if __name__ == '__main__':
    unittest.main()
