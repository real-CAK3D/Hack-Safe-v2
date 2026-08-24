class Plugin:
    name = 'quickdic'
    description = 'Tiny offline cheat-sheet/dictionary inspired by helper plugins.'

    def on_status(self, status):
        return {'title': 'QuickDic', 'lines': ['SSID: Wi-Fi network name', 'BSSID: AP MAC address', 'RSSI/signal: radio strength', 'LAN: local network']}
