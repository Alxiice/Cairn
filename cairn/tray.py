"""The Cairn server in the system tray, detached from any terminal.

    py -m cairn start    start the tray server if it is not running (detached), then open the app window
    py -m cairn tray     the tray server itself, in this process (what `start` launches)
    py -m cairn stop | restart

Tray menu: Open Cairn (the desktop window, on this server), Open in the browser, API console (/docs),
data folder, log, Restart, Stop. Closing the app window or the terminal leaves the server running; Stop ends it.
Works where pystray has a backend: Windows, macOS, and Linux with AppIndicator or an X11 tray. Without one, the
server runs without an icon (`py -m cairn stop` or `restart`).
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent  # the folder holding the cairn package
ICON = PACKAGE_ROOT / "assets" / "tray-icon.png"
HOME = Path.home() / ".cairn"
LOG = HOME / "server.log"


def url_of(host: str, port: int) -> str:
    return f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}"


def running(url: str, timeout: float = 1.0) -> bool:
    """True if a Cairn server answers there."""
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=timeout) as r:
            return b'"cairn"' in r.read()
    except OSError:
        return False


def port_free(host: str, port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def spawn_detached(args: list[str]) -> subprocess.Popen:
    """`python -m cairn <args>` in a process of its own: no console, not killed with the terminal."""
    exe = Path(sys.executable)
    kw: dict = {"cwd": str(PACKAGE_ROOT), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL, "close_fds": True}
    if sys.platform == "win32":
        gui = exe.with_name("pythonw.exe")
        exe = gui if gui.is_file() else exe
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        try:  # leave the terminal's job object too, so closing Windows Terminal does not take us down
            return subprocess.Popen([str(exe), "-m", "cairn", *args], creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kw)
        except OSError:
            return subprocess.Popen([str(exe), "-m", "cairn", *args], creationflags=flags, **kw)
    return subprocess.Popen([str(exe), "-m", "cairn", *args], start_new_session=True, **kw)


def server_args(host: str, port: int, data: str, plugins: list[str], blender: str) -> list[str]:
    args = ["--host", host, "--port", str(port), "--data", str(Path(data).resolve())]
    if plugins:
        args += ["--plugins", *[str(Path(p).resolve()) for p in plugins]]
    if blender:
        args += ["--blender", blender]
    return args


def start(host: str, port: int, data: str, plugins: list[str], blender: str, window: bool = True) -> int:
    """Starts the tray server unless one already answers, then opens the app window on it."""
    url = url_of(host, port)
    if not running(url):
        spawn_detached(["tray", *server_args(host, port, data, plugins, blender)])
        end = time.time() + 30
        while not running(url):
            if time.time() > end:
                print(f"Cairn did not start: see {LOG}", file=sys.stderr)
                return 1
            time.sleep(0.2)
    if window:
        spawn_detached(["desktop", "--server", url])
    print(f"Cairn runs at {url} (system tray)")
    return 0


def control(host: str, port: int, action: str) -> int:
    """Asks a running tray server to stop or restart (the same as its menu)."""
    url = url_of(host, port)
    try:
        urllib.request.urlopen(urllib.request.Request(f"{url}/api/server/{action}", method="POST"), timeout=3).read()
    except OSError as e:
        print(f"No Cairn tray server at {url} ({e})")
        return 1
    print(f"Cairn: {action} requested")
    return 0


def _open(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606 - a file or folder of our own
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


class TrayServer:
    def __init__(self, host: str, port: int, data: str, plugins: list[str], blender: str):
        self.host, self.port, self.data, self.plugins, self.blender = host, port, data, plugins, blender
        self.url = url_of(host, port)
        self.server = None
        self.thread: threading.Thread | None = None
        self.icon = None
        self.done = threading.Event()

    def serve(self) -> None:
        import uvicorn
        from .api import create_app
        app = create_app(self.data, self.plugins, self.blender)
        app.state.stop_server = lambda: threading.Thread(target=self.quit, daemon=True).start()
        app.state.restart_server = lambda: threading.Thread(target=self.restart, daemon=True).start()
        self.server = uvicorn.Server(uvicorn.Config(app, host=self.host, port=self.port, log_level="info"))
        self.thread = threading.Thread(target=self.server.run, daemon=True, name="cairn server")
        self.thread.start()

    def shutdown_server(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout=10)

    def quit(self) -> None:
        self.shutdown_server()
        if self.icon is not None:
            self.icon.stop()
        self.done.set()

    def restart(self) -> None:
        """A new process (new code, plugins and settings) once this one has let the port go."""
        self.shutdown_server()
        spawn_detached(["tray", "--wait", *server_args(self.host, self.port, self.data, self.plugins, self.blender)])
        if self.icon is not None:
            self.icon.stop()
        self.done.set()

    def menu(self):
        import pystray
        item = pystray.MenuItem
        return pystray.Menu(
            item(f"Cairn · {self.url}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("Open Cairn", lambda: spawn_detached(["desktop", "--server", self.url]), default=True),
            item("Open in the browser", lambda: webbrowser.open(self.url)),
            item("API console", lambda: webbrowser.open(self.url + "/docs")),
            item("Data folder", lambda: _open(Path(self.data))),
            item("Server log", lambda: _open(LOG)),
            pystray.Menu.SEPARATOR,
            item("Restart", lambda: threading.Thread(target=self.restart, daemon=True).start()),
            item("Stop", lambda: threading.Thread(target=self.quit, daemon=True).start()),
        )

    def run(self) -> int:
        try:
            import pystray
            from PIL import Image
            self.icon = pystray.Icon("cairn", Image.open(ICON), f"Cairn · {self.url}", self.menu())
        except Exception as e:  # no tray backend (a Linux desktop without AppIndicator or X11 tray): no icon
            print(f"No system tray ({type(e).__name__}: {e}); the server runs without an icon", flush=True)
            self.icon = None
        self.serve()
        if self.icon is not None:
            self.icon.run()  # until Stop or Restart
        else:
            self.done.wait()
        self.shutdown_server()
        return 0


def run_tray(host: str, port: int, data: str, plugins: list[str], blender: str, wait: bool = False) -> int:
    HOME.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log  # pythonw has none; a terminal-less process keeps its log here
    url = url_of(host, port)
    end = time.time() + (20 if wait else 0)
    while not port_free(host, port):
        if running(url) and not wait:
            print(f"Cairn already runs at {url}", flush=True)
            return 0
        if time.time() > end:
            print(f"Port {port} is taken: another program uses it", flush=True)
            return 1
        time.sleep(0.25)
    print(f"Cairn tray server at {url}, data in {data}", flush=True)
    return TrayServer(host, port, data, plugins, blender).run()
