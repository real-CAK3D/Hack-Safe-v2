class Plugin:
    name = 'load_watch'
    description = 'Toggleable high-load watch: flags hot CPU processes and likely dashboard load causes.'

    def on_status(self, status):
        procs = (status.get('system') or {}).get('top_processes') or []
        lines = []
        for p in procs[:6]:
            try:
                cpu = float(p.get('cpu') or 0)
            except Exception:
                cpu = 0
            cmd = p.get('command') or 'process'
            if cpu >= 8 or cmd in ('MainThread', 'chromium', 'python3', 'node'):
                lines.append(f"{cmd} pid {p.get('pid')} CPU {p.get('cpu')}% MEM {p.get('memory')}%")
        if any('MainThread' in line for line in lines):
            lines.append('Likely cause: God’s Eye Vite dev server on :4173; use static fallback/disable live when idle.')
        return {'title': 'Load Watch', 'lines': lines or ['No major hot process in cached sample.']}
