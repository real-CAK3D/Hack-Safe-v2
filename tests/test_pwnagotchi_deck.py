import unittest

from spac3ghost.collectors import (
    build_owned_lab_capture_plan,
    pwn_channel_plan,
    parse_iw_dev_interfaces,
    parse_iw_phy_channels,
)


class PwnagotchiDeckTests(unittest.TestCase):
    def test_parse_iw_phy_channels(self):
        text = """
		* 2412 MHz [1] (20.0 dBm)
		* 2437 MHz [6] (20.0 dBm)
		* 2462 MHz [11] (20.0 dBm)
		* 2484 MHz [14] (disabled)
"""
        self.assertEqual(parse_iw_phy_channels(text), [1, 6, 11])

    def test_parse_iw_dev_interfaces(self):
        text = """
phy#0
	Interface wlan0
		type managed
		channel 6 (2437 MHz), width: 20 MHz
	Interface wlan1mon
		type monitor
"""
        self.assertEqual(parse_iw_dev_interfaces(text), [
            {"name": "wlan0", "type": "managed", "channel": 6},
            {"name": "wlan1mon", "type": "monitor", "channel": None},
        ])

    def test_channel_plan_prioritizes_populated_channels(self):
        networks = [
            {"ssid": "Home", "channel": "6", "signal": "80"},
            {"ssid": "Lab", "channel": "1", "signal": "50"},
            {"ssid": "Guest", "channel": "6", "signal": "40"},
        ]
        plan = pwn_channel_plan(networks, supported_channels=[1, 6, 11])
        self.assertEqual(plan[0]["channel"], 6)
        self.assertEqual(plan[0]["aps"], 2)
        self.assertEqual(plan[-1]["channel"], 11)

    def test_capture_plan_requires_owned_lab_gate(self):
        refused = build_owned_lab_capture_plan("wlan1mon", bssid="AA:BB:CC:DD:EE:FF", channel=6, owned_lab=False)
        self.assertFalse(refused["ok"])
        self.assertIn("owned lab", refused["error"].lower())
        allowed = build_owned_lab_capture_plan("wlan1mon", bssid="AA:BB:CC:DD:EE:FF", channel=6, owned_lab=True)
        self.assertTrue(allowed["ok"])
        self.assertIn("airodump-ng", allowed["argv"])
        self.assertIn("--bssid", allowed["argv"])
        self.assertNotIn("aireplay-ng", allowed["argv"])


if __name__ == "__main__":
    unittest.main()
