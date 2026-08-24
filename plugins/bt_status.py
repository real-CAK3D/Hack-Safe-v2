class Plugin:
    name = 'bt_status'
    description = 'Native bt-tether/status style plugin: reports Bluetooth controller state and nearby/cached devices.'

    def on_status(self, status):
        bt = status.get('bluetooth', {})
        names = ', '.join((d.get('name') or d.get('mac')) for d in bt.get('devices', [])[:4]) or 'none'
        return {'title': 'Bluetooth Status', 'lines': [
            f"Powered: {bt.get('powered')}",
            f"Devices: {len(bt.get('devices', []))}",
            f"Seen: {names}",
        ]}
