import time

class Plugin:
    name = 'session_stats'
    description = 'Native version of Pwnagotchi session-stats: counts current-session observations.'

    def __init__(self):
        self.started = int(time.time())
        self.max_wifi = 0
        self.max_bt = 0
        self.max_lan = 0

    def on_status(self, status):
        self.max_wifi = max(self.max_wifi, len(status.get('wifi', {}).get('networks', [])))
        self.max_bt = max(self.max_bt, len(status.get('bluetooth', {}).get('devices', [])))
        self.max_lan = max(self.max_lan, len(status.get('lan', {}).get('devices', [])))
        return {
            'title': 'Session Stats',
            'lines': [
                f"Runtime: {int((time.time() - self.started) / 60)} min",
                f"Max Wi-Fi seen: {self.max_wifi}",
                f"Max Bluetooth seen: {self.max_bt}",
                f"Max LAN seen: {self.max_lan}",
            ]
        }
