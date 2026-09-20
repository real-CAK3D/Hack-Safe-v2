class Plugin:
    name = 'vision_history'
    description = 'Toggleable Vision history summary; deletion is handled by the Vision tab Clear History button.'

    def on_status(self, status):
        hist = status.get('vision_history') or {}
        count = hist.get('count', 0)
        items = hist.get('items') or []
        labels = []
        for row in items[:3]:
            labels.append(', '.join(row.get('labels') or []) or 'no detections')
        return {'title': 'Vision History', 'lines': [f'Captured scans: {count}', 'Clear from Vision tab.', *(labels or ['No recent scans.'])]}
