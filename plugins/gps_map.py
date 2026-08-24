class Plugin:
    name = 'gps_map'
    description = 'Safe webgpsmap style plugin: shows local GPS map link when a fix exists.'

    def on_status(self, status):
        gps = status.get('sensors', {}).get('gps', {})
        if gps.get('lat') and gps.get('lon'):
            link = f"https://www.openstreetmap.org/?mlat={gps['lat']}&mlon={gps['lon']}#map=16/{gps['lat']}/{gps['lon']}"
            lines = [f"Fix: {gps.get('modeLabel')}", f"Lat/Lon: {gps.get('lat')}, {gps.get('lon')}", link]
        else:
            lines = [f"Fix: {gps.get('modeLabel', 'NO DATA')}", 'No map link until GPS fix.']
        return {'title': 'GPS Map', 'lines': lines}
