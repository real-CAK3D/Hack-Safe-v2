#!/usr/bin/env bash
# Start Spac3-Gh0st (Pi or Linux/macOS dev box). Env overrides:
#   SPAC3GHOST_HOST / SPAC3GHOST_PORT / SPAC3GHOST_ROOT / SPAC3GHOST_DATA
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
exec "$PY" -m spac3ghost.app 2>&1 | tee -a logs/server.log
