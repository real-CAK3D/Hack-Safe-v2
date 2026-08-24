from spac3ghost.collectors import known_wifi_passwords

class Plugin:
    name = 'wifi_audit'
    description = 'Defensive Wi-Fi audit: checks locally saved passwords for length/obvious weakness; no cracking or capture.'

    def on_status(self, status):
        data = known_wifi_passwords(True)
        weak = []
        total = 0
        for n in data.get('networks', []):
            if not n.get('has_password'):
                continue
            total += 1
            pw = n.get('password') or ''
            if len(pw) < 12 or pw.lower() in ('password', 'password12345678', '12345678', 'qwerty123'):
                weak.append(n.get('ssid') or n.get('name'))
        return {'title': 'Wi-Fi Audit', 'lines': [
            f'Saved Wi-Fi PSKs audited: {total}',
            f'Weak/short candidates: {len(weak)}',
            ', '.join(weak[:4]) if weak else 'No obvious short saved PSKs.',
            'No handshake capture/cracking automation in safe mode.',
        ]}
