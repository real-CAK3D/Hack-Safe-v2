import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spac3ghost.collectors import (
    build_owned_lab_capture_plan,
    handshake_capture_status,
    pwn_channel_plan,
    parse_iw_dev_interfaces,
    parse_iw_phy_channels,
    start_owned_lab_capture,
    stop_owned_lab_capture,
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
	Unnamed/non-netdev interface
		type P2P-device
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

    def test_capture_lifecycle_tracks_artifacts_and_blocks_overlap(self):
        class FakeProc:
            pid = 43210

        adapter = {
            "interfaces": [{"name": "wlan1mon", "type": "monitor"}],
            "tools": {"airodump-ng": True},
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_file = tmp_path / "handshake_capture.json"
            handshakes = tmp_path / "handshakes"
            calls = []

            def fake_popen(argv, stdout=None, stderr=None, start_new_session=False):
                calls.append(argv)
                return FakeProc()

            with patch("spac3ghost.collectors.HANDSHAKE_DIR", handshakes), \
                 patch("spac3ghost.collectors.CAPTURE_STATE_FILE", state_file), \
                 patch("spac3ghost.collectors._iw_capabilities", return_value=adapter), \
                 patch("spac3ghost.collectors._pid_alive", return_value=False):
                result = start_owned_lab_capture({"owned_lab": True, "interface": "wlan1mon", "bssid": "AA:BB:CC:DD:EE:FF", "channel": 6}, popen_factory=fake_popen)
                self.assertTrue(result["ok"])
                self.assertEqual(calls[0][:2], ["airodump-ng", "-w"])
                self.assertIn("--bssid", calls[0])
                self.assertNotIn("aireplay-ng", calls[0])
                cap_file = handshakes / (Path(result["prefix"]).name + "-01.cap")
                cap_file.write_bytes(b"pcap placeholder")
                status = handshake_capture_status()
                self.assertFalse(status["running"])
                self.assertEqual(status["pcaps"][0]["name"], cap_file.name)

            with patch("spac3ghost.collectors.HANDSHAKE_DIR", handshakes), \
                 patch("spac3ghost.collectors.CAPTURE_STATE_FILE", state_file), \
                 patch("spac3ghost.collectors._iw_capabilities", return_value=adapter), \
                 patch("spac3ghost.collectors._pid_alive", return_value=True):
                blocked = start_owned_lab_capture({"owned_lab": True, "interface": "wlan1mon"}, popen_factory=fake_popen)
                self.assertFalse(blocked["ok"])
                self.assertIn("already running", blocked["error"])

            with patch("spac3ghost.collectors.HANDSHAKE_DIR", handshakes), \
                 patch("spac3ghost.collectors.CAPTURE_STATE_FILE", state_file), \
                 patch("spac3ghost.collectors._pid_alive", return_value=False):
                stopped = stop_owned_lab_capture()
                self.assertTrue(stopped["ok"])
                self.assertFalse(stopped["stopped"])


if __name__ == "__main__":
    unittest.main()
