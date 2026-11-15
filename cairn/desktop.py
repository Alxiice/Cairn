"""The desktop app: a native window (pywebview: WebView2, WKWebView or WebKitGTK) on the web UI.

It starts a local server on a free port, or connects to a remote one. The window adds what a browser cannot do,
through `window.pywebview.api`: open a version in Blender and open a folder, on this machine.
"""
from __future__ import annotations

import socket
import threading
import time
import urllib.request
from pathlib import Path

from .blender import BlenderError, find_blender, open_folder, open_in_blender

APP_ICON = Path(__file__).resolve().parent.parent / "assets" / "app-icon.png"  # rendered by assets/make_icons.py


class Bridge:
    """Methods the web UI calls (window.pywebview.api.*). Paths come from our own server."""

    def __init__(self, blender: str):
        self.blender = blender

    def open_in_blender(self, path: str) -> str:
        exe = find_blender(self.blender)
        if not exe:
            return "Blender not found: set it in ~/.cairn/settings.json (\"blender\")"
        try:
            open_in_blender(exe, Path(path))
        except BlenderError as e:
            return str(e)
        return ""

    def pick_folder(self) -> str:
        """A native folder dialog (Settings → Plugins → Browse). "" when cancelled."""
        import webview
        result = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else ""

    def open_folder(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"{p} not found on this machine"
        open_folder(p if p.is_dir() else p.parent)
        return ""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url: str, seconds: float = 15) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(url + "/api/health", timeout=1).read()
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"The server did not start at {url}")


def run(data: str, plugins: list[str], blender: str, server: str = "") -> int:
    import sys
    if sys.stderr is None:  # pythonw (Cairn.bat): no console, keep the server's log in a file
        log = Path.home() / ".cairn" / "cairn.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(log, "w", encoding="utf-8", buffering=1)
    if sys.platform == "win32":  # own taskbar identity: otherwise Windows groups us with pythonw.exe and shows its icon
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Cairn.Desktop")
    import webview
    url = server.rstrip("/")
    if not url:
        import uvicorn
        from .api import create_app
        port = _free_port()
        srv = uvicorn.Server(uvicorn.Config(create_app(data, plugins, blender), host="127.0.0.1", port=port, log_level="warning"))
        threading.Thread(target=srv.run, daemon=True, name="cairn server").start()
        url = f"http://127.0.0.1:{port}"
    _wait(url)
    webview.create_window("Cairn", url, js_api=Bridge(blender), width=1440, height=900, min_size=(1000, 640),
                          background_color="#0d1016")
    # WinForms (Windows) only takes an .ico; GTK and Qt take a PNG. Absolute: the working folder varies.
    webview.start(icon=str(APP_ICON.with_suffix(".ico" if sys.platform == "win32" else ".png")))
    return 0
