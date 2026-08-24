class Plugin:
    name = 'gpio_tilt'
    description = 'GPIO button/tilt style plugin: reacts to CrowPi tilt sensor events.'

    def on_status(self, status):
        sensors = status.get('sensors', {})
        gpio = sensors.get('gpio', {})
        tilt = sensors.get('tilt_event', {})
        return {'title': 'GPIO/Tilt', 'lines': [
            f"Tilt: {gpio.get('tiltLabel', 'n/a')}",
            f"Changed: {tilt.get('changed')} fast={tilt.get('fast')}",
            f"Previous: {tilt.get('previous')}",
        ]}
