from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_idle_screen_ui_removed():
    combined = "\n".join((ROOT / p).read_text(errors="replace") for p in ["web/index.html", "web/app.js", "web/style.css"])
    assert "idleButton" not in combined
    assert "toggleIdle" not in combined
    assert "idle-mode" not in combined
    assert "Idle Screen" not in combined


def test_pwnagotchi_capture_ui_present():
    app_js = (ROOT / "web/app.js").read_text(errors="replace")
    assert "PWNAGOTCHI RF DECK" in app_js
    assert "pwnChannelRows" in app_js
    assert "startOwnedLabCapture" in app_js
    assert "/api/pwnagotchi/capture" in app_js


def test_capture_api_route_present():
    app_py = (ROOT / "spac3ghost/app.py").read_text(errors="replace")
    assert "/api/pwnagotchi/capture" in app_py
    assert "start_owned_lab_capture" in app_py
