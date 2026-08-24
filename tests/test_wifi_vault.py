import unittest

from spac3ghost.collectors import parse_nmcli_connection_names, split_nmcli


class WifiVaultTests(unittest.TestCase):
    def test_parse_nmcli_connection_names_filters_wifi(self):
        text = 'Home\\:Lab:802-11-wireless\nlo:loopback\nEthernet:802-3-ethernet\n'
        rows = parse_nmcli_connection_names(text)
        self.assertEqual(rows, [{'name': 'Home:Lab', 'type': '802-11-wireless'}])

    def test_split_nmcli_unescapes_colons(self):
        self.assertEqual(split_nmcli('a\\:b:c'), ['a:b', 'c'])


if __name__ == '__main__':
    unittest.main()
