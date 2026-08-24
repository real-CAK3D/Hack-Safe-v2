class Plugin:
    name = 'command_center'
    description = 'Command-center helper: gives exact SSH/tunnel commands without embedding a terminal.'

    def on_status(self, status):
        ips = status.get('system', {}).get('ips', [])
        ts = next((ip for ip in ips if ip.startswith('100.')), '100.75.120.80')
        return {'title': 'Command Center', 'lines': [
            f'SSH: ssh pi@{ts}',
            f'Tunnel UI: ssh -L 8765:127.0.0.1:8765 pi@{ts}',
            'Then open http://127.0.0.1:8765 on your client.',
            'Shell access stays outside this dashboard.',
        ]}
