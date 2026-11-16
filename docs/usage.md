# Using Cairn

## The tray menu

Right-click the tray icon for the menu (a left click opens the app):

- the server's address;
- **Open Cairn**: the app window;
- **Open in the browser**;
- **API console**: FastAPI's interactive API docs (`/docs`);
- **Data folder** and **Server log** (`~/.cairn/server.log`);
- **Restart**: a new process, which picks up new code, plugins and settings;
- **Stop**.

## Commands

| Command | What it does |
|---|---|
| `python -m cairn start [--no-window]` | What the launchers run: starts the tray server if none answers on the port, then opens the app window. |
| `python -m cairn stop` / `restart` | Stops or restarts the tray server (from its own machine only). |
| `python -m cairn tray` | The tray server in this process (what `start` launches). |
| `python -m cairn` | The app window on a private server that ends with the window (no tray). |
| `python -m cairn desktop --server http://host:8765` | The app window on a running server: yours, or someone else's. |
| `python -m cairn serve --host 0.0.0.0 --port 8765` | The server only, in this terminal. Other machines open `http://<machine>:8765`. |

Options: `--host` and `--port` (default `127.0.0.1:8765`), `--data DIR` (where the database lives), `--plugins DIR …`, `--blender EXE`. Their defaults can be set in `~/.cairn/settings.json`: `dataDir`, `pluginFolders`, `blender`, `server`, `host`, `port`.

## Sharing a project

Run `python -m cairn serve --host 0.0.0.0` (or set `host` in the settings) on one machine and open its address from the others, in a browser or with `python -m cairn desktop --server <address>`.

!!! warning "No login yet"
    Anyone who can reach the server can change everything. Share it on a trusted network only.

## Task templates

A new shot or asset gets the default template of its kind, or another one picked in the **New** dialog. Its page can then add custom tasks, remove tasks, or apply another template. Tasks the new template does not list are removed, or disabled when they have versions. Custom tasks stay.

Templates are edited in **Settings**, along with the default template for new shots and the one for new assets.

## Versions

Versions are files in the project folder on the server, and they are never overwritten:

- `shots/<shot>/<task>/<variant>/<shot>_<task>_<variant>_v001.blend`
- `assets/<type>/<asset>/<task>/<variant>/…`

A version can be published as an empty `.blend` (made by Blender on the server), as a copy of another version, or by uploading a file from your computer, which also works with a remote server. Everything else (shots, assets, tasks, statuses, notes, links) is in the database.

**Open in Blender** needs the desktop app on the server's machine, or a path shared between machines. In a browser, the file is downloaded instead.

## Deleting

Deleting a shot or an asset removes its records (tasks, versions, casting, note links) but **never its files**: they stay in the project folder. Publishing again under the same name skips the version numbers already taken. Deleting a sequence keeps its shots.

## Plugins

Add a plugin folder in **Settings → Plugins → Add the folder** (the app window has **Browse…**). See [Plugins](plugins.md).
