class Plugin:
    name = 'memtemp'
    description = 'Native version of Pwnagotchi memtemp: reports memory, CPU temperature, and disk.'

    def on_status(self, status):
        system = status.get('system', {})
        return {
            'title': 'MemTemp',
            'lines': [
                f"CPU temp: {system.get('cpu_temp_f', 'n/a')} F",
                f"Disk: {system.get('disk_root', 'n/a')}",
                f"Uptime: {int(system.get('uptime_s', 0) / 60)} min",
            ]
        }
