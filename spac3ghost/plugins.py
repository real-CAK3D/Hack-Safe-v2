from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

from .config import load_config

PLUGIN_DIR = Path('/home/pi/spac3-gh0st/plugins')


class PluginManager:
    """Tiny Pwnagotchi-like plugin callback dispatcher for safe local plugins."""

    def __init__(self, plugin_dir: Path = PLUGIN_DIR):
        self.plugin_dir = plugin_dir
        self.plugins: List[Any] = []
        self.enabled: Dict[str, bool] = {}

    def load(self) -> None:
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.plugins = []
        self.enabled = load_config().get('plugins', {})
        for path in sorted(self.plugin_dir.glob('*.py')):
            name = path.stem
            if self.enabled.get(name, True) is False:
                continue
            spec = importlib.util.spec_from_file_location(f'spac3_plugin_{name}', path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            plugin = getattr(module, 'Plugin', None)
            instance = plugin() if plugin else module
            instance._spac3_path = str(path)
            self.plugins.append(instance)
            self.call('on_loaded', instance)

    def reload(self) -> None:
        self.load()

    def call(self, callback: str, *args, **kwargs) -> List[Any]:
        results = []
        targets = [args[0]] if args and args[0] in self.plugins else self.plugins
        call_args = args[1:] if args and args[0] in self.plugins else args
        for plugin in targets:
            fn = getattr(plugin, callback, None)
            if callable(fn):
                try:
                    results.append(fn(*call_args, **kwargs))
                except Exception as exc:
                    results.append({'plugin': plugin.__class__.__name__, 'error': str(exc)})
        return results

    def describe(self) -> List[Dict[str, Any]]:
        items = []
        enabled = load_config().get('plugins', {})
        loaded_names = {getattr(p, 'name', p.__class__.__name__) for p in self.plugins}
        for path in sorted(self.plugin_dir.glob('*.py')):
            name = path.stem
            loaded = next((p for p in self.plugins if getattr(p, 'name', p.__class__.__name__) == name), None)
            callbacks = []
            description = ''
            if loaded is not None:
                callbacks = [n for n in dir(loaded) if n.startswith('on_') and callable(getattr(loaded, n))]
                description = getattr(loaded, 'description', '')
            items.append({
                'name': name,
                'enabled': enabled.get(name, True) is not False,
                'loaded': name in loaded_names,
                'description': description,
                'callbacks': sorted(callbacks),
                'path': str(path),
            })
        return items
