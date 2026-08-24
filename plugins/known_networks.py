class Plugin:
    name = 'known_networks'
    description = 'Native grid-ish plugin: summarizes known/new Wi-Fi, Bluetooth, and LAN sightings.'

    def on_status(self, status):
        wifi = status.get('wifi', {})
        bt = status.get('bluetooth', {})
        lan = status.get('lan', {})
        return {'title': 'Known Networks', 'lines': [
            f"Wi-Fi visible: {len(wifi.get('networks', []))} new={wifi.get('new_count', 0)} cached={wifi.get('cached')}",
            f"Bluetooth known: {len(bt.get('devices', []))} new={bt.get('new_count', 0)} cached={bt.get('cached')}",
            f"LAN neighbors: {len(lan.get('devices', []))} new={lan.get('new_count', 0)} cached={lan.get('cached')}",
        ]}
