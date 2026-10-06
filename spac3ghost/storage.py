"""SD-card-friendly file writes.

The Pi runs off an SD card, which wears out from many small rewrites and can be
left with a truncated file if power drops mid-write. Everything that persists
JSON state should go through ``write_json`` so that:

- an unchanged payload never touches the disk, and
- a write is atomic (temp file + rename): after a power cut you get either the
  old file or the new one, never an empty/half-written one.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_text(path: Path, text: str) -> bool:
    """Atomically write ``text`` to ``path``. Returns False if it was already identical."""
    path = Path(path)
    try:
        if path.read_bytes() == text.encode('utf-8'):
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    try:
        tmp.write_bytes(text.encode('utf-8'))
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return True


def write_json(path: Path, data: Any, **dumps_kwargs: Any) -> bool:
    """Atomically write ``data`` as JSON, skipping the write when nothing changed."""
    return write_text(path, json.dumps(data, **dumps_kwargs))
