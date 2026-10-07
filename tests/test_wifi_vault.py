import unittest
from unittest import mock

from spac3ghost.collectors import known_wifi_passwords, parse_nmcli_connection_names, split_nmcli

LIST_OUT = 'Home:802-11-wireless\nCafe:802-11-wireless\n'


def _detail(psk, key_mgmt='wpa-psk'):
    return f'802-11-wireless.ssid:                     HomeSSID\n802-11-wireless-security.key-mgmt:         {key_mgmt}\n802-11-wireless-security.psk:              {psk}\n'


class KnownWifiPasswordsTests(unittest.TestCase):
    def _run(self, plain_psk, sudo_psk, reveal):
        calls = []

        def fake_run(cmd, timeout=8):
            calls.append(cmd)
            if cmd[:3] == ['nmcli', '-t', '-f']:
                return LIST_OUT
            if cmd[0] == 'sudo':
                return _detail(sudo_psk)
            return _detail(plain_psk)

        with mock.patch('spac3ghost.collectors.run', side_effect=fake_run):
            return known_wifi_passwords(reveal), calls

    def test_reveal_falls_back_to_sudo_when_plain_nmcli_is_denied(self):
        # nmcli prints "--" when the process has no active login session (e.g. started over SSH).
        out, calls = self._run('--', 'hunter22', reveal=True)
        self.assertEqual({n['password'] for n in out['networks']}, {'hunter22'})
        self.assertTrue(any(c[:2] == ['sudo', '-n'] for c in calls))
        self.assertFalse(out['networks'][0]['secret_unavailable'])

    def test_no_sudo_unless_the_reveal_toggle_is_on(self):
        out, calls = self._run('--', 'hunter22', reveal=False)
        self.assertFalse(any(c[0] == 'sudo' for c in calls))
        self.assertTrue(all(n['has_password'] for n in out['networks']))
        self.assertTrue(all(n['password'] == '••••••••' for n in out['networks']))

    def test_plain_read_that_works_never_uses_sudo(self):
        out, calls = self._run('realpass', 'other', reveal=True)
        self.assertEqual(out['networks'][0]['password'], 'realpass')
        self.assertFalse(any(c[0] == 'sudo' for c in calls))

    def test_unreadable_secret_is_reported_not_shown_as_blank(self):
        out, _ = self._run('--', '--', reveal=True)
        row = out['networks'][0]
        self.assertEqual(row['password'], '')
        self.assertTrue(row['has_password'])
        self.assertTrue(row['secret_unavailable'])

    def test_open_network_has_no_password(self):
        def fake_run(cmd, timeout=8):
            if cmd[:3] == ['nmcli', '-t', '-f']:
                return 'Open:802-11-wireless\n'
            return '802-11-wireless.ssid:                     Open\n802-11-wireless-security.psk:              --\n'
        with mock.patch('spac3ghost.collectors.run', side_effect=fake_run):
            out = known_wifi_passwords(True)
        self.assertFalse(out['networks'][0]['has_password'])


class WifiVaultTests(unittest.TestCase):
    def test_parse_nmcli_connection_names_filters_wifi(self):
        text = 'Home\\:Lab:802-11-wireless\nlo:loopback\nEthernet:802-3-ethernet\n'
        rows = parse_nmcli_connection_names(text)
        self.assertEqual(rows, [{'name': 'Home:Lab', 'type': '802-11-wireless'}])

    def test_split_nmcli_unescapes_colons(self):
        self.assertEqual(split_nmcli('a\\:b:c'), ['a:b', 'c'])


if __name__ == '__main__':
    unittest.main()
