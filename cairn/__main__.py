"""Command line.

    python -m cairn start [--no-window]     the server in the system tray (detached, survives the terminal), then the app window
    python -m cairn stop | restart          stops or restarts the tray server
    python -m cairn tray                    the tray server in this process (what `start` launches)
    python -m cairn                         desktop app on its own private server, closed with the window
    python -m cairn desktop --server URL    desktop app on a running server (yours in the tray, or someone else's)
    python -m cairn serve [--host 0.0.0.0] [--port 8765] [--data DIR] [--plugins DIR ...] [--blender EXE]
Settings: ~/.cairn/settings.json (dataDir, pluginFolders, blender, server, host, port).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SETTINGS = Path.home() / ".cairn" / "settings.json"
OLD_HOME = Path.home() / ".b3dprod"  # Cairn was named B3DProd until 0.4.2


def migrate_home() -> None:
    """Moves B3DProd's folder (settings, data, logs) to ~/.cairn, once."""
    if OLD_HOME.is_dir() and not SETTINGS.parent.exists():
        OLD_HOME.rename(SETTINGS.parent)


def settings() -> dict:
    defaults = {"dataDir": str(Path.home() / ".cairn" / "data"), "pluginFolders": [], "blender": "", "server": "",
                "host": "127.0.0.1", "port": 8765}
    try:
        return {**defaults, **json.loads(SETTINGS.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return defaults


def main(argv=None) -> int:
    migrate_home()
    s = settings()
    ap = argparse.ArgumentParser(prog="cairn")
    sub = ap.add_subparsers(dest="cmd")
    sv = sub.add_parser("serve", help="run the server only (open http://host:port in a browser or the desktop app)")
    st = sub.add_parser("start", help="the server in the system tray, detached, then the app window")
    st.add_argument("--no-window", action="store_true", help="only make sure the tray server runs")
    tr = sub.add_parser("tray", help="the tray server in this process")
    tr.add_argument("--wait", action="store_true", help=argparse.SUPPRESS)  # restart: wait for the old process
    sp = sub.add_parser("stop", help="stop the tray server")
    rs = sub.add_parser("restart", help="restart the tray server (new code, plugins and settings)")
    for p in (sv, st, tr, sp, rs):
        p.add_argument("--host", default=s["host"], help="0.0.0.0 to share on the network (no authentication yet)")
        p.add_argument("--port", type=int, default=s["port"])
    for p in (sv, st, tr, sub.add_parser("desktop", help="the desktop window (default)")):
        p.add_argument("--data", default=s["dataDir"], help="where the database lives")
        p.add_argument("--plugins", nargs="*", default=s["pluginFolders"], help="plugin folders")
        p.add_argument("--blender", default=s["blender"], help="Blender executable (else found automatically)")
    sub.choices["desktop"].add_argument("--server", default=s["server"], help="use a running server instead of a private one")
    args = ap.parse_args(argv)
    if args.cmd == "serve":
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(args.data, args.plugins, args.blender), host=args.host, port=args.port, log_level="info")
        return 0
    if args.cmd in ("start", "tray", "stop", "restart"):
        from . import tray
        if args.cmd in ("stop", "restart"):
            return tray.control(args.host, args.port, args.cmd)
        if args.cmd == "start":
            return tray.start(args.host, args.port, args.data, args.plugins, args.blender, window=not args.no_window)
        return tray.run_tray(args.host, args.port, args.data, args.plugins, args.blender, wait=args.wait)
    if args.cmd is None:
        args = ap.parse_args(["desktop"] + (argv or []))
    from .desktop import run
    return run(args.data, args.plugins, args.blender, args.server)


if __name__ == "__main__":
    raise SystemExit(main())
