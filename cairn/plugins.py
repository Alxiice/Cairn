"""Server plugins. A plugin is a folder with plugin.json:

    {"id": "cow", "name": "COW", "description": "Cinematic Outer Wilds", "version": "0.1.0",
     "icon": "icon.svg", "server": "cow_plugin:register", "ui": "ui"}

- `server` (optional): `module:function`, imported with the plugin folder on sys.path. `function(ctx)` returns a
  FastAPI APIRouter, mounted at /api/plugins/<id>. `ctx` has `store`, `blender()` and `data_dir`.
- `ui` (optional): a folder of static files served at /plugins/<id>/, its index.html shown as the plugin's workspace.
  It may link /theme.css for the app's colors and call its own API with relative URLs.
- `icon`: an SVG drawn in the workspace rail (currentColor strokes follow the app's colors).
A plugin that fails to load is listed with its error and never stops the server.
"""
from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Plugin:
    id: str
    name: str
    folder: Path
    description: str = ""
    version: str = "0"
    icon: str = ""          # SVG markup
    ui: Path | None = None
    server: str = ""
    error: str = ""
    router: Any = None

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description, "version": self.version,
                "icon": self.icon, "ui": f"/plugins/{self.id}/" if self.ui else "", "error": self.error}


@dataclass
class PluginContext:
    store: Any
    data_dir: Path
    helpers: dict = field(default_factory=dict)


def discover(folders: list[str | Path]) -> list[Plugin]:
    found: dict[str, Plugin] = {}
    for folder in map(Path, folders):
        candidates = [folder] + (sorted(d for d in folder.iterdir() if d.is_dir()) if folder.is_dir() else [])
        for d in candidates:
            manifest = d / "plugin.json"
            if not manifest.is_file():
                continue
            try:
                m = json.loads(manifest.read_text(encoding="utf-8"))
                p = Plugin(id=m["id"], name=m.get("name", m["id"]), folder=d, description=m.get("description", ""),
                           version=m.get("version", "0"), server=m.get("server", ""))
                if m.get("icon") and (d / m["icon"]).is_file():
                    p.icon = (d / m["icon"]).read_text(encoding="utf-8")
                if m.get("ui") and (d / m["ui"]).is_dir():
                    p.ui = d / m["ui"]
            except (ValueError, KeyError, OSError) as e:
                p = Plugin(id=d.name, name=d.name, folder=d, error=f"bad plugin.json: {e}")
            found.setdefault(p.id, p)
    return list(found.values())


def load(plugin: Plugin, ctx: PluginContext) -> None:
    """Imports the plugin's server part; errors land in plugin.error."""
    if plugin.error or not plugin.server:
        return
    module_name, _, func = plugin.server.partition(":")
    if str(plugin.folder) not in sys.path:
        sys.path.insert(0, str(plugin.folder))
    try:
        plugin.router = getattr(importlib.import_module(module_name), func or "register")(ctx)
    except Exception as e:  # a broken plugin must not take the server down
        plugin.error = f"{type(e).__name__}: {e}"
