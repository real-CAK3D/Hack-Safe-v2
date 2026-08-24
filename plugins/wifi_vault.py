from spac3ghost.collectors import known_wifi_passwords

class Plugin:
    name = 'wifi_vault'
    description = 'Local-only known Wi-Fi password vault. Masks by default; UI can reveal via /api/wifi/passwords?reveal=1.'

    def on_status(self, status):
        data = known_wifi_passwords(False)
        count = len(data.get('networks', []))
        with_pw = sum(1 for n in data.get('networks', []) if n.get('has_password'))
        return {'title': 'Wi-Fi Vault', 'lines': [f"Saved Wi-Fi profiles: {count}", f"Passwords available locally: {with_pw}", 'Open Tools -> Known Wi-Fi Passwords to reveal.']}
