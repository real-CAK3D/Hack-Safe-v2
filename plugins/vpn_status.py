from spac3ghost.controls import camera_status, vpn_status
from spac3ghost.config import load_config


class Plugin:
    name = 'vpn_status'
    description = 'VPN status/control companion: toggles configured NetworkManager VPN/WireGuard profiles only.'

    def on_status(self, status):
        vpn = vpn_status()
        selected = vpn.get('selected_profile') or {}
        active = vpn.get('active_connections') or []
        lines = [
            f"Proton installed: {'yes' if vpn.get('proton_installed') else 'no'}",
            f"Configured VPN profiles: {len(vpn.get('profiles') or [])}",
            f"Selected: {selected.get('name', 'none')}",
            f"Active: {', '.join(item['name'] for item in active) or 'none'}",
            f"Tools found: {', '.join(vpn.get('tools') or []) or 'none'}",
            vpn.get('message') or '',
        ]
        return {'title': 'VPN Status', 'lines': lines}
