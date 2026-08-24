import json
import time
from pathlib import Path

class Plugin:
    name = 'net_position'
    description = 'Safe local version of net-pos: records strongest nearby APs with current GPS/sensor context, no upload.'

    def on_wifi_scan(self, data):
        gps = {}
        path = Path('/home/pi/spac3-gh0st/data/net-position-log.jsonl')
        nets = sorted(data.get('networks', []), key=lambda n: int(n.get('signal') or 0), reverse=True)[:5]
        rec = {'ts': int(time.time()), 'top_wifi': nets, 'note': 'local-only; no external geolocation/upload'}
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a') as f:
            f.write(json.dumps(rec) + '\n')
        return {'logged': len(nets), 'path': str(path)}

    def on_status(self, status):
        path = Path('/home/pi/spac3-gh0st/data/net-position-log.jsonl')
        lines = path.read_text(errors='ignore').splitlines() if path.exists() else []
        return {'title': 'Net Position', 'lines': [f"Local AP snapshots: {len(lines)}", 'No upload; local-only log.', str(path)]}
