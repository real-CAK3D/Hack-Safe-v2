"""Test isolation: never touch a real Spac3-Gh0st data dir or config."""
import os
import sys
import tempfile
from pathlib import Path

os.environ['SPAC3GHOST_DATA'] = tempfile.mkdtemp(prefix='spac3ghost-test-')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
