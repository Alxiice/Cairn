# Cairn

A production tracker and asset manager for Blender projects: sequences, shots and assets, their tasks, every published version, notes and review.

## Plan

- A Python server (FastAPI + SQLite) that holds every rule and the project files.
- A web UI (Svelte 5 + TypeScript) that only talks to the server's HTTP API, shown in a desktop window or a browser.
- The server runs in the system tray; several machines can use the same server.
- Game- or project-specific tools come as plugins.

The detailed plan follows in `docs/development-plan.md`.
