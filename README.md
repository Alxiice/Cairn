<img src="assets/logo.svg" alt="Cairn" height="64">

**Cairn** is a production tracker and asset manager for small Blender projects. It helps organizing:
- sequences
- shots
- assets

And organize the production around tasks, and manage the production through versionned published files, notes with replies and attachments, and review of renders side by side.

This is aimed to be a tool that helps creators to organize and manage their project go from the start to the end. It integrates a plugin system to help adding specific tools for projects.

## Run

Needs Python 3.11+ (tested on 3.13), Node 20+ only to build the UI.

```powershell
py -m pip install -r requirements.txt
cd web; npm install; npm run build; cd ..
```

Then double-click **`Cairn.bat`** (Windows) or run **`./cairn.sh`** (Linux, macOS). It starts the server **in the system tray**, detached: closing the terminal does not stop it, and closing the app window leaves it running. It then opens the app window. Run it again: it reuses the running server and opens another window.

**Tray menu** (right click; a left click opens the app): the server's address, **Open Cairn** (the app window), **Open in the browser**, **API console** (FastAPI's interactive docs, `/docs`), **Data folder**, **Server log** (`~/.cairn/server.log`), **Restart** (a new process: new code, plugins and settings), **Stop**.

Linux: pystray needs a tray. On GNOME, install the AppIndicator extension (and `gir1.2-ayatanaappindicator3-0.1` or similar); on other desktops the X11 tray works. Without a tray the server still runs, with no icon.

| Command | What |
|---|---|
| `py -m cairn start [--no-window]` | What the launchers run: the tray server if none answers on the port (detached), then the app window. |
| `py -m cairn stop` / `restart` | Stop or restart the tray server (from its machine only). |
| `py -m cairn tray` | The tray server in this process (what `start` launches). |
| `py -m cairn` | The app window on a private server that ends with the window (no tray). |
| `py -m cairn desktop --server http://host:8765` | The app window on a running server: yours, or someone else's. |
| `py -m cairn serve --host 0.0.0.0 --port 8765` | The server only, in this terminal: open `http://<machine>:8765` from other machines. **No login yet: trusted network only.** |
| Options | `--host`, `--port` (default 127.0.0.1:8765), `--data DIR` (database), `--plugins DIR …`, `--blender EXE`. Defaults: `~/.cairn/settings.json` (`dataDir`, `pluginFolders`, `blender`, `server`, `host`, `port`). |

**Plugins** (COW for Outer Wilds): **Settings → Plugins → Add the folder**, e.g. `E:\Documents\TRAVAIL\OW\apps\CinematicOW` (**Browse…** in the app window). The plugin loads at once and appears in the left rail; the server remembers the folder (`<data>/server.json`). Folders can also be given at start (`--plugins`, or `pluginFolders` in `~/.cairn/settings.json`).

**Task templates**: a new shot or asset gets its kind's default template, or another picked in the New dialog. Its page can then add custom tasks, remove tasks, or apply another template (tasks the new template does not list are removed, or disabled when they have versions; custom tasks stay).

**Versions** are files in the project folder on the server, never overwritten: `shots/<shot>/<task>/<variant>/<shot>_<task>_<variant>_v001.blend`, `assets/<type>/<asset>/<task>/<variant>/…` (Cairn 0.3's layout). Publish: an empty `.blend` (Blender on the server), a copy of another version, or a file uploaded from this computer (so it works with a remote server). Everything else (entities, tasks, statuses, notes, links) is in the SQLite database.

**Deleting** a shot or asset removes its records (tasks, versions, casting, note links) but never its files: they stay in the project folder. Deleting a sequence keeps its shots.

**Open in Blender** needs the desktop app on the server's machine (or a shared path); in a browser the file is downloaded instead.


## Tests

```powershell
py -m pip install -r requirements-dev.txt
py -m pytest                               # store, API (FastAPI TestClient, a fake plugin) and tray server
cd web; npm run check; npm run build       # types and build
```

## Not yet

Login and permissions (the server is single-user: everything is done as "You"), version-level casting in the UI beyond publish, packaging (installers).

## License

Apache-2.0, see `LICENSE` and `NOTICE`. Dependencies keep their own licenses: all permissive except pystray (LGPL-3.0), which Cairn only imports, unmodified.
