# Contributing to Cairn

Thanks for helping. This page explains how to set up a development copy, how Cairn is built, and the few rules that keep it working.

## Set up

You need Python 3.11 or newer and Node 20.19 or newer.

```powershell
# Windows (PowerShell)
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
cd web; npm install; npm run build; cd ..
```

```sh
# Linux, macOS
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
(cd web && npm install && npm run build)
```

`requirements-dev.txt` adds the test and documentation tools to the app's own `requirements.txt`.

To work on the UI with live reload, run the server in one terminal (`python -m cairn serve --data <a test folder>`) and `npm run dev` in `web/` in another, then open the address Vite prints. It forwards API calls to the server.

## Tech stack

- **Server**: Python, [FastAPI](https://fastapi.tiangolo.com/) for the HTTP API, served by Uvicorn, and SQLite (Python's built-in `sqlite3`) for the database.
- **Web UI**: [Svelte 5](https://svelte.dev/) (with runes) and TypeScript, built with Vite. No UI framework: the components and the themes are our own.
- **Desktop window**: [pywebview](https://pywebview.flowrl.com/), which shows the web UI in the system's own browser engine (WebView2 on Windows, WebKit on macOS and Linux).
- **System tray**: [pystray](https://github.com/moses-palmer/pystray), with Pillow for the icon.
- **Tests**: pytest, with FastAPI's test client for the API.
- **Docs**: MkDocs with the Material theme.

## Architecture

Cairn is a server and a web page that talks to it.

The **server** holds everything: the database, the project files and every rule about them. Its heart is `cairn/store.py`. Every change to the data goes through one of its methods, which checks the input, writes everything in a single database transaction, records the change in the activity feed and announces it. The store knows nothing about HTTP, so it can be tested on its own.

On top of the store, `cairn/api.py` exposes the HTTP API. Its routes are thin: they read the request, call the store and return the result. Request bodies are checked by pydantic models: that is where untrusted input from clients is validated. The API also streams live events (Server-Sent Events on `/api/events`), so every open window refreshes as soon as someone changes something. It serves the built web UI and the plugins' pages too.

The **web UI** in `web/` never reads files or the database: it only calls the HTTP API. This is what lets one machine serve a project to several others. The few things a browser cannot do, such as opening a file in Blender or showing a folder, go through the desktop window's bridge (`cairn/desktop.py`). In a plain browser those buttons fall back to something sensible, such as downloading the file.

The **desktop app** is the same web UI in a native window. It starts a private server, or connects to a running one.

The **tray server** (`cairn/tray.py`) runs the server in the background with an icon in the system tray, so it keeps running after you close the window or the terminal. The launchers (`Cairn.bat`, `cairn.sh`) start it and open a window.

**Plugins** add project-specific tools without touching Cairn. A plugin is a folder with a `plugin.json`: it can add API routes, which receive the store, and a web page, shown as a workspace in the app. See [the plugin format](docs/plugins.md).

**Version files** live in the project folder, with a path built from the shot or asset, the task, the variant and the version number. Everything else is in the database.

## Rules

- **Never overwrite or delete a version file.** Deleting a shot or an asset removes its database records only. Publishing reserves a version number first and skips numbers already taken on disk.
- **Rules live in the store.** Do not validate or write data in the API routes or in the UI.
- **The UI only talks to the API.** Anything it needs from the server becomes an API route.
- **Cairn stays generic.** Nothing specific to one game or project: that belongs in a plugin.
- **Colors are theme variables.** Never hardcode a color in a component: add a variable to both themes in `web/public/theme.css`.
- **Uploads go through the API** with a size limit. The server never reads a path sent by a client.
- **English only**, in code, UI text, docs and file names.

## Checks

Run them before you open a pull request. The GitHub workflows run them too.

```sh
python -m pytest                  # store, API and tray server
cd web; npm run check; npm run build   # types and build
mkdocs build --strict             # documentation
```

## Documentation

The documentation is in `docs/` and builds with `mkdocs serve` (live preview) or `mkdocs build`. Update it, the README and `CHANGELOG.md` in the same pull request as the change they describe.

## Branches and commits

Work on a branch named after what it does (`feat/…`, `fix/…`, `docs/…`) and open a pull request into `main`. Write commit messages as a short sentence saying what the commit does, such as "Add the review page.". Keep each commit to one step that works on its own.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE), like the rest of Cairn.
