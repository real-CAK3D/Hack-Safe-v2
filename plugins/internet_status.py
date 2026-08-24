import socket

class Plugin:
    name = 'internet_status'
    description = 'Grid/internet-available style plugin: quick connectivity status.'

    def on_status(self, status):
        ok = False
        try:
            socket.create_connection(('1.1.1.1', 53), timeout=0.4).close()
            ok = True
        except Exception:
            pass
        return {'title': 'Internet Status', 'lines': [f'Internet reachable: {ok}', f'Tailscale IPs: {" ".join(ip for ip in status.get("system", {}).get("ips", []) if ip.startswith("100.")) or "none"}']}
