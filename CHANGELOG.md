# Changelog

## 0.1.0: 2026-11-16

First version: a production tracker and asset manager for Blender projects. A Python server (FastAPI + SQLite) holds every rule; a web UI (Svelte 5 + TypeScript) only calls its HTTP API, in a native desktop window (pywebview) on Windows, macOS and Linux, or in a browser on other machines.

- **Data**: projects, sequences, shots and assets, task templates, tasks (status, enabled, custom), uses (an asset in a shot or in another asset, no loops), versions (any file or folder, never overwritten), notes linked to shots, assets, versions and tasks, with replies, attachments and assignees, activity.
- **Task templates**: a default per kind, a choice at creation, custom tasks, remove (disabled when versions exist), apply another template.
- **Delete** sequences (their shots stay, without a sequence), shots and assets: their records leave the database, **version files stay on disk**, and publishing again under the same name skips the numbers taken.
- **Blender**: find it, publish an empty `.blend`, open a version (desktop window).
- **Workspaces**: Home, Sequences, Shots (tracker table, a dash for a task a shot does not have), Assets (library with facets, cards or list), shot and asset pages, Review (compare two versions, draw on a frame, note with the drawing attached), Notes, Settings, plugin workspaces with their icon. Search with Ctrl K. Live updates for every client (Server-Sent Events).
- **Themes**: dark, light or like the system, per window, shared with plugin pages (`theme.css`, `theme.js`).
- **Plugins**: server routes, a static UI and a rail icon (`docs/plugins.md`). Plugin folders are added in Settings (loaded at once, remembered in `<data>/server.json`) or given at start.
- **System tray server** (`python -m cairn start`, `Cairn.bat`, `cairn.sh`): starts detached, survives the terminal and the app window, a second start reuses it. Tray menu: Open Cairn, Open in the browser, API console (`/docs`), Data folder, Server log, Restart, Stop. Also `python -m cairn stop` / `restart` (local only).
- **Desktop window**: the Cairn icon in the window and the taskbar, a native folder picker, Open in Blender and Open folder.
- **Tests**: store and API (with a fake plugin), tray server.
