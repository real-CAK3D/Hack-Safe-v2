from pathlib import Path

from spac3ghost.paths import LOG_DIR

class Plugin:
    name = 'logtail'
    description = 'Native version of Pwnagotchi logtail: shows recent Spac3-Gh0st backend log lines.'

    def on_status(self, status):
        path = LOG_DIR / 'server.log'
        if not path.exists():
            lines = ['No server.log yet.']
        else:
            lines = path.read_text(errors='ignore').splitlines()[-4:]
            lines = [line[-100:] for line in lines] or ['Log is quiet.']
        return {'title': 'Logtail', 'lines': lines}
