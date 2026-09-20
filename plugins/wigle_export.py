from pathlib import Path

from spac3ghost.paths import DATA_DIR

class Plugin:
    name = 'wigle_export'
    description = 'Safe version of Wigle plugin: prepares local Wi-Fi observation count only; no automatic upload.'

    def on_status(self, status):
        wifi = status.get('wifi', {})
        export = DATA_DIR / 'wigle-local-export.csv'
        return {'title': 'WiGLE Export', 'lines': [
            f"Current Wi-Fi observations: {len(wifi.get('networks', []))}",
            'Auto-upload disabled by design.',
            f"Export path: {export}",
        ]}
