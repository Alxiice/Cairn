# Development plan

How Cairn is built, in the order of the repository's history. Read the commits of `develop` from the first one: each step builds on the previous ones.

## Principles

- **A server and a web UI.** The server (Python, FastAPI, SQLite) holds every rule; the UI (Svelte 5, TypeScript) only calls its HTTP API. So one machine can serve a project to several, and the desktop app is the same UI in a native window.
- **Rules in one place.** `cairn/store.py` validates, writes in one transaction, logs the activity and announces the change. `cairn/api.py` stays thin.
- **Files are never lost.** A version is a new file, never overwritten nor deleted, even when its shot or asset leaves the tracker.
- **Generic.** Nothing about a particular game: game tools are plugins (routes, a static UI and a rail icon).

## Steps

1. **Identity**: a README with this plan, an empty changelog, the ignore rules, then the logo and the icons (with the scripts that render them).
2. **Backend** (branch `feature/backend`, merged into `develop`):
   1. Python dependencies.
   2. The store: the schema (projects, sequences, task templates, shots and assets, tasks, uses, versions, notes, replies, attachments, activity) and its rules.
   3. Plugins: discovery and loading.
   4. Blender: find it, create an empty `.blend`, open a file.
   5. The HTTP API: routes, uploads, Server-Sent Events, plugin routes, the built UI.
   6. The system tray server (detached start, single instance, restart, stop).
   7. The command line.
3. **Frontend** (branch `feature/frontend`, merged into `develop`):
   1. The Vite + Svelte + TypeScript project.
   2. The dark and light themes (CSS variables shared with plugin pages).
   3. The API client, the app state (project, live events, routing, messages) and the desktop actions.
   4. Shared components: dialogs, pickers, status pills, thumbnails, the side panel.
   5. The pages: welcome and home; sequences, shots, assets and the shot or asset page; review and notes; settings and plugin pages.
   6. The app shell: the workspace rail, the project menu, search and routing.
   7. The desktop window (pywebview, with its bridge) and the launchers.
4. **Docs and tests**: the plugin format, the store, API and tray tests, the full README and the changelog.

## Checks

```powershell
python -m pytest
cd web; npm run check; npm run build
```
