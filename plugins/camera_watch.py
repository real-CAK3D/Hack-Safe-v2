from spac3ghost.controls import camera_status


class Plugin:
    name = 'camera_watch'
    description = 'Camera/vision readiness plugin: privacy-safe status with manual opt-in toggle.'

    def on_status(self, status):
        cam = camera_status()
        return {'title': 'Camera Watch', 'lines': [
            f"Vision toggle: {'ON' if cam.get('enabled') else 'OFF'}",
            f"Camera visible: {'yes' if cam.get('camera_available') else 'no'} ({cam.get('device')})",
            f"USB/Pi camera: {'yes' if cam.get('usb_camera_available') else 'no'}/{'yes' if cam.get('pi_camera_available') else 'no'}",
            f"Video devices: {len(cam.get('video_devices') or [])}",
            ', '.join((cam.get('video_devices') or [])[:4]) if cam.get('video_devices') else 'No /dev/video* devices found.',
            f"AI backend: {cam.get('ai_backend')} {'ready' if cam.get('ai_available') else 'not ready'}",
            cam.get('message') or '',
        ]}
