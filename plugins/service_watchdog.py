class Plugin:
    name = 'service_watchdog'
    description = 'Native version of Pwnagotchi watchdog: flags important local services that are down.'

    def on_status(self, status):
        down = [name for name, info in status.get('services', {}).items() if not info.get('active')]
        return {
            'title': 'Service Watchdog',
            'lines': ['All watched services active.'] if not down else [f"DOWN: {name}" for name in down]
        }
