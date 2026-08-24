import unittest

from spac3ghost.collectors import parse_nmcli_wifi, parse_bluetooth_devices, mac_vendor_hint, _annotate_tilt_event


class CollectorTests(unittest.TestCase):
    def test_parse_nmcli_wifi_colon_escaped_rows(self):
        text = "yes:Space\\:Brigade:40:80:WPA2\nno:LabNet:6:55:WPA1 WPA2\n"
        rows = parse_nmcli_wifi(text)
        self.assertEqual(rows[0]["ssid"], "Space:Brigade")
        self.assertTrue(rows[0]["connected"])
        self.assertEqual(rows[1]["channel"], "6")

    def test_parse_bluetooth_devices(self):
        text = "Device AA:BB:CC:DD:EE:FF Keyboard\nDevice 11:22:33:44:55:66 Phone\n"
        rows = parse_bluetooth_devices(text)
        self.assertEqual(rows[0]["mac"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(rows[1]["name"], "Phone")

    def test_mac_vendor_hint_known_prefix(self):
        self.assertEqual(mac_vendor_hint("2C:CF:67:00:00:00"), "Raspberry Pi")

    def test_tilt_raw_zero_is_rendered_level_and_flat(self):
        status = _annotate_tilt_event({'gpio': {'tilt': 0}})
        self.assertEqual(status['gpio']['tiltOrientation'], 'LEVEL')
        self.assertEqual(status['gpio']['tiltAngle'], 0)
        self.assertEqual(status['tilt_event']['orientation'], 'LEVEL')
        self.assertEqual(status['tilt_event']['angle'], 0)

    def test_tilt_raw_one_is_rendered_as_tripped_tilt(self):
        status = _annotate_tilt_event({'gpio': {'tilt': 1}})
        self.assertEqual(status['gpio']['tiltOrientation'], 'TILTED')
        self.assertEqual(status['gpio']['tiltAngle'], 28)


if __name__ == "__main__":
    unittest.main()
