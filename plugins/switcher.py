import time

class Plugin:
    name = 'switcher'
    description = 'Task switcher style plugin: rotates suggested actions.'

    def on_status(self, status):
        tasks = ['Check Wi-Fi field', 'Review known devices', 'Watch services', 'Refresh sensors', 'Open Tools tab']
        task = tasks[int(time.time() / 15) % len(tasks)]
        return {'title': 'Switcher', 'lines': [f'Current suggested action: {task}']}
