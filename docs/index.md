# Cairn

**Cairn** is a production tracker and asset manager for small Blender projects. It organizes a project's sequences, shots and assets and the tasks to make them. Every published version is kept as a file, and the team works through notes with replies and attachments and reviews renders side by side.

It aims to help creators take a project from start to finish. A plugin system adds tools specific to a project or a game.

Cairn is a server and a web UI. The server keeps the database and the project files. The UI runs in a desktop window or in a browser, so one machine can serve a project to several others.

[Install Cairn](install.md){ .md-button .md-button--primary } [Use it](usage.md){ .md-button }

## Workspaces

| Workspace | |
|---|---|
| **Home** | Tasks in progress (retakes and reviews first), activity, progress by sequence, recently updated shots and assets. |
| **Sequences** | Add, rename, describe, reorder and delete sequences (their shots stay, without a sequence). The selected one lists its shots, with **+ Shot** and **Delete**. |
| **Shots** | The tracker table: one row per shot, grouped by sequence (fold, progress), one column per task with its status (editable in place) and latest version, open notes, last update. A dash means the shot has no such task. Click a row for the side panel; double-click it or click its name for the shot's page. |
| **Assets** | The library: facets (type, overall status, task, used or not), cards with a size slider (at its minimum, a list), and a side panel with the pipeline, what the asset uses and where it is used. |
| **Shot or asset page** | The task pipeline: status, versions, **+** to publish, **✕** to remove (a task with versions is disabled instead, its history kept), **+ custom task**, **Apply a template…**. Tabs: Versions (filter by task, latest only, Open in Blender, Review, Note), Notes, Assets or Uses, Used in. A details panel (title, description, sequence or type, head and tail, cut in and out). Click the thumbnail to choose an image. |
| **Review** | Pick a shot or asset and a version (a video, an image, or a render folder's color layer). Compare two versions with a wipe or side by side, step frame by frame at the project's frame rate, follow the note marks on the timeline, draw on the frame and post a note with the drawing attached, optionally setting the task to Retake. |
| **Notes** | Open, assigned to me, closed, all. Each thread links to shots, assets, versions and tasks, holds attachments (images shown) and replies. |
| **Settings** | Project details and asset types, task templates, appearance (dark, light or like the system), plugins and plugin folders, the server. |
| **Search** (++ctrl+k++) | Shots, assets, versions and notes, with keyboard navigation. |
| **Plugins** | Each plugin can add its own workspace to the rail, with its icon. |

## Not yet

- Login and permissions: the server is single-user, everything is done as "You". Share it on a trusted network only.
- Version-level casting in the UI beyond publishing.
- Installers.
