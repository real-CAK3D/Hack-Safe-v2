import unittest

from spac3ghost.personality import Spac3Voice, choose_mood


class DarkFaceChatterTests(unittest.TestCase):
    def test_dark_mode_cycles_through_multiple_faces(self):
        status = {'system': {'cpu_temp_c': 40}, 'wifi': {}, 'lan': {}, 'bluetooth': {}, 'sensors': {'light': {'lux': 2}}}
        faces = {choose_mood(status, now=ts)['face'] for ts in range(0, 20)}
        self.assertGreaterEqual(len(faces), 3)

    def test_dark_voice_has_many_phrases(self):
        voice = Spac3Voice(seed=3)
        samples = {voice.light(1) for _ in range(40)}
        self.assertGreaterEqual(len(samples), 5)

    def test_context_chatter_includes_network_and_plugin_lines(self):
        voice = Spac3Voice(seed=5)
        status = {
            'wifi': {'networks': [{'ssid': 'A'}, {'ssid': 'B'}]},
            'bluetooth': {'devices': [{'name': 'Speaker'}]},
            'lan': {'devices': [{'ip': '1.2.3.4'}]},
            'native_plugins': [{'loaded': True}, {'loaded': False}],
        }
        samples = {voice.chatter(status) for _ in range(50)}
        self.assertTrue(any('Wi-Fi' in x or 'SSID' in x for x in samples))
        self.assertTrue(any('Bluetooth' in x or 'blue' in x for x in samples))
        self.assertTrue(any('plugin' in x.lower() for x in samples))


if __name__ == '__main__':
    unittest.main()
