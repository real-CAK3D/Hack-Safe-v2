class Plugin:
    name = 'safe_mode'
    description = 'Safety banner: documents what Spac3-Gh0st deliberately will not automate.'

    def on_status(self, status):
        return {'title': 'Safe Mode', 'lines': ['Passive/local by default.', 'No deauth. No phishing. No credential capture.', 'Lab features only for your own gear.']}
