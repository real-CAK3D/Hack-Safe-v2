class Plugin:
    name = 'screen_refresh'
    description = 'Display refresh style plugin: reports UI refresh/caching behavior.'

    def on_status(self, status):
        return {'title': 'Screen Refresh', 'lines': ['Dashboard refresh: 2.5s', f"Wi-Fi cached: {status.get('wifi',{}).get('cached')}", f"Sensors cached: {status.get('sensors',{}).get('cached')}"]}
