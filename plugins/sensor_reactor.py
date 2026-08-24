class Plugin:
    name = 'sensor_reactor'
    description = 'Native GPS/CrowPi sensor status plugin inspired by Pwnagotchi gps/webgpsmap UI plugins.'

    def on_status(self, status):
        sensors = status.get('sensors', {})
        gps = sensors.get('gps', {})
        indoor = sensors.get('indoor', {})
        light = sensors.get('light', {})
        gpio = sensors.get('gpio', {})
        return {
            'title': 'Sensor Reactor',
            'lines': [
                f"GPS: {gps.get('modeLabel', 'n/a')} sats {gps.get('satellitesUsed') or 0}/{gps.get('satellitesVisible') or 0}",
                f"Indoor: {indoor.get('tempF', 'n/a')} F / {indoor.get('humidity', 'n/a')}%",
                f"Light: {light.get('lux', 'n/a')} lux",
                f"Tilt: {gpio.get('tiltLabel', 'n/a')}",
            ]
        }
