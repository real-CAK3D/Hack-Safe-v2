import unittest
from unittest import mock

from spac3ghost.personality import FACE, Spac3Voice, choose_mood, event_from_status


class PersonalityTests(unittest.TestCase):
    def test_choose_mood_gets_alert_for_new_discoveries(self):
        status = {"wifi": {"new_count": 1}, "lan": {"new_count": 0}, "bluetooth": {"new_count": 0}, "system": {"cpu_temp_c": 45}}
        mood = choose_mood(status)
        self.assertEqual(mood["name"], "alert")
        self.assertIn(mood["face"], {FACE["LOOK_R"], FACE["LOOK_L"], FACE["DEBUG"], "(@_@)"})

    def test_choose_mood_gets_hot_for_high_temperature(self):
        status = {"wifi": {"new_count": 0}, "lan": {"new_count": 0}, "bluetooth": {"new_count": 0}, "system": {"cpu_temp_c": 81}}
        mood = choose_mood(status)
        self.assertEqual(mood["name"], "hot")
        self.assertEqual(mood["face"], FACE["INTENSE"])

    def test_choose_mood_gets_lonely_when_offline_and_no_devices(self):
        status = {"wifi": {"connected": False, "networks": []}, "lan": {"devices": []}, "bluetooth": {"devices": []}, "system": {"cpu_temp_c": 40}}
        mood = choose_mood(status)
        self.assertEqual(mood["name"], "lonely")
        self.assertEqual(mood["face"], FACE["LONELY"])

    def test_voice_has_many_responses_for_wifi_scan(self):
        voice = Spac3Voice(seed=7)
        samples = {voice.wifi_scan(12) for _ in range(30)}
        self.assertGreaterEqual(len(samples), 4)

    def test_action_phrase_banks_have_at_least_ten_lines(self):
        voice = Spac3Voice(seed=1)
        required = [
            'starting', 'idle', 'wifi_scan', 'bluetooth_scan', 'lan_scan', 'new_thing',
            'gps_no_fix', 'gps_fix', 'hot', 'warm', 'dark', 'bright', 'service_down',
            'service_up', 'service_toggle', 'settings_saved', 'sensors_refreshed',
            'vision_on', 'vision_off', 'vpn', 'yolo_seen', 'yolo_empty', 'network_chatter', 'pranks'
        ]
        phrases = voice.config.get('phrases', {})
        missing = [key for key in required if len(phrases.get(key, [])) < 10]
        self.assertEqual(missing, [])

    def test_goblin_references_are_reduced_in_phrase_banks(self):
        voice = Spac3Voice(seed=1)
        all_lines = '\n'.join(line for vals in voice.config.get('phrases', {}).values() if isinstance(vals, list) for line in vals)
        self.assertNotIn('goblin', all_lines.lower())

    def test_event_from_status_reports_gps_fix(self):
        status = {"sensors": {"gps": {"fixed": True, "modeLabel": "3D FIX", "satellitesUsed": 6}}}
        # GPS is the fallback report when no time-of-day/ambient phrase applies.
        with mock.patch('spac3ghost.personality.choose_mood', return_value={'name': 'curious'}):
            event = event_from_status(status)
        self.assertIn("GPS", event["text"])
        self.assertEqual(event["kind"], "gps")


if __name__ == "__main__":
    unittest.main()
