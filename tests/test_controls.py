import unittest
from unittest.mock import patch

from spac3ghost.controls import camera_status, vpn_status
from spac3ghost.personality import choose_mood
from spac3ghost.vision import available_yolo_model, configured_feeds, select_feed, vision_backend_status


class ControlsTests(unittest.TestCase):
    def test_vpn_status_reports_unconfigured_without_profiles(self):
        with patch('spac3ghost.controls._cmd_output', return_value=''):
            status = vpn_status()
        self.assertFalse(status['configured'])
        self.assertFalse(status['proton_installed'])
        self.assertEqual(status['button_label'], 'Open Proton')

    def test_vpn_status_does_not_show_second_open_proton_when_gui_running(self):
        def fake_output(cmd, timeout=4):
            text = ' '.join(cmd)
            if 'command -v protonvpn-app' in text:
                return '/usr/bin/protonvpn-app'
            if 'pgrep -f protonvpn-app' in text:
                return '1234'
            return ''
        with patch('spac3ghost.controls._cmd_output', side_effect=fake_output):
            status = vpn_status()
        self.assertFalse(status['configured'])
        self.assertTrue(status['proton_installed'])
        self.assertTrue(status['gui_running'])
        self.assertEqual(status['button_label'], 'VPN Off')

    def test_camera_status_is_opt_in_and_reports_ai(self):
        status = camera_status()
        self.assertIn('enabled', status)
        self.assertIn('camera_available', status)
        self.assertIn('ai_backend', status)
        self.assertIn('button_label', status)
        self.assertIn('frame_url', status)
        self.assertIn('ai_available', status)
        self.assertIn('feeds', status)
        self.assertTrue(any(feed.get('id') == 'local' for feed in status['feeds']))
        self.assertTrue(any(feed.get('id') == 'bak3ry' for feed in status['feeds']))

    def test_configured_feeds_support_local_and_bak3ry_toggle(self):
        cfg = {'device': '/dev/video0', 'feeds': [{'id': 'bak3ry', 'label': 'theBAK3RY Cam', 'source': 'url', 'snapshot_url': 'http://thebak3ry:9999/shot.jpg'}]}
        feeds = configured_feeds(cfg)
        self.assertEqual(feeds[0]['id'], 'local')
        self.assertEqual(select_feed(cfg, 'bak3ry')['snapshot_url'], 'http://thebak3ry:9999/shot.jpg')

    def test_yolo_backend_detects_local_model_when_present(self):
        model = available_yolo_model()
        status = vision_backend_status()
        if model:
            self.assertEqual(status['backend'], 'yolo')
            self.assertTrue(status['available'])
        else:
            self.assertFalse(status['available'])

    def test_idle_faces_cycle_for_curious_mood(self):
        status = {'wifi': {'connected': True, 'networks': ['x']}, 'lan': {}, 'bluetooth': {}, 'sensors': {'light': {}}}
        faces = {choose_mood(status, now=t)['face'] for t in range(0, 6)}
        self.assertGreater(len(faces), 1)


if __name__ == '__main__':
    unittest.main()
