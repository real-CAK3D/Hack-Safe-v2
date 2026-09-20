class Plugin:
    name = 'launch_bay'
    description = 'Toggleable plugin panel listing openable local tools/services with safe URLs and state notes.'

    def on_status(self, status):
        sw = (((status.get('lab_toys') or {}).get('software') or {}).get('modules') or [])
        wanted = ['projectnomad', 'uptimekuma', 'docker', 'ollama', 'openwebui', 'hermesworkspace', 'godseye', 'jellyfin', 'syncthing']
        by_id = {m.get('id'): m for m in sw}
        lines = []
        for sid in wanted:
            m = by_id.get(sid)
            if not m:
                continue
            label = m.get('label') or sid
            state = 'running' if m.get('running') else 'stopped'
            url = m.get('url') or 'no browser UI'
            lines.append(f'{label}: {state} // {url}')
        if not lines:
            lines = ['Launch Bay waiting for lab software status.']
        return {'title': 'Launch Bay', 'lines': lines[:10]}
