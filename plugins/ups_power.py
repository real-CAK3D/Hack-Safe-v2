from pathlib import Path

class Plugin:
    name = 'ups_power'
    description = 'UPS/power status style plugin: reports undervoltage flags if available.'

    def on_status(self, status):
        throttled = Path('/sys/devices/platform/soc/soc:firmware/get_throttled')
        lines = ['Power throttle data not exposed here.']
        try:
            if throttled.exists():
                lines = [f'get_throttled: {throttled.read_text().strip()}']
        except Exception as exc:
            lines = [f'Power check error: {exc}']
        return {'title': 'UPS/Power', 'lines': lines}
