#!/usr/bin/env python3
"""Example native Spac3-Gh0st plugin."""

class Plugin:
    name = "ghost_logger"

    def on_loaded(self):
        return "ghost_logger loaded"

    def on_status(self, status):
        # Called whenever /api/status is requested.
        return None

    def on_wifi_scan(self, data):
        return {"saw": len(data.get("networks", []))}

    def on_bluetooth_scan(self, data):
        return {"saw": len(data.get("devices", []))}

    def on_lan_scan(self, data):
        return {"saw": len(data.get("devices", []))}
