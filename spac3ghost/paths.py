"""Central filesystem locations.

Nothing here is hard-coded to ``/home/pi`` any more. Defaults work both on the
Raspberry Pi (repo deployed at ``~/spac3-gh0st``) and on a dev machine (repo
checked out anywhere), and can be overridden with environment variables:

- ``SPAC3GHOST_ROOT``  project root (default: the folder containing this package)
- ``SPAC3GHOST_DATA``  runtime data dir (default: ``<root>/data``)
- ``SPAC3GHOST_HOME``  home dir used to find optional third-party apps (default: ``~``)
- ``SPAC3GHOST_RUNTIME``  RAM-backed dir for fast-churning state that is fine to
  lose on reboot (default: ``/dev/shm/spac3ghost`` on Linux, else ``<data>/runtime``).
  Keeping it off the SD card is what stops the Pi from wearing the card out.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get('SPAC3GHOST_ROOT') or Path(__file__).resolve().parent.parent)
HOME = Path(os.environ.get('SPAC3GHOST_HOME') or Path.home())
DATA_DIR = Path(os.environ.get('SPAC3GHOST_DATA') or ROOT / 'data')
_SHM = Path('/dev/shm')
RUNTIME_DIR = Path(os.environ.get('SPAC3GHOST_RUNTIME') or (_SHM / 'spac3ghost' if _SHM.is_dir() else DATA_DIR / 'runtime'))
LOG_DIR = ROOT / 'logs'
WEB_DIR = ROOT / 'web'
PLUGIN_DIR = ROOT / 'plugins'
