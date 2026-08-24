import subprocess

class Plugin:
    name = 'auto_update_check'
    description = 'Safe auto-update style plugin: reports apt upgrade count; never applies updates automatically.'

    def __init__(self):
        self._cached = None
        self._ticks = 0

    def on_status(self, status):
        self._ticks += 1
        if self._cached is None or self._ticks % 80 == 1:
            try:
                out = subprocess.run(['apt', 'list', '--upgradable'], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=6).stdout
                count = max(0, len([l for l in out.splitlines() if '/' in l]) - 0)
                self._cached = [f'Upgradeable packages: {count}', 'Auto-apply disabled.', 'Use terminal when you want updates.']
            except Exception as exc:
                self._cached = [f'Update check unavailable: {exc}']
        return {'title': 'Auto Update Check', 'lines': self._cached}
