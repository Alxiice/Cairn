# Plugins

A plugin is a folder with a `plugin.json`. The server loads the plugins of its **plugin folders**; a plugin folder is a plugin, or holds plugin folders (`E:\Documents\TRAVAIL\OW\apps\CinematicOW` holds `cow/`).

Adding a plugin folder:

- **Settings → Plugins → Add the folder** (the app window has **Browse…**). The plugins load at once, their workspace appears in the rail, and the server remembers the folder in `<data>/server.json`. Removing a folder there takes effect at the next restart (loaded code cannot be unloaded). Only the server's own machine may add or remove folders (`POST/DELETE /api/plugin-folders`).
- At start: `--plugins DIR …`, or `pluginFolders` in `~/.cairn/settings.json`.

```json
{
  "id": "cow",
  "name": "COW",
  "description": "Cinematic Outer Wilds: film the game for the project",
  "version": "0.1.0",
  "icon": "icon.svg",
  "server": "cow_server:register",
  "ui": "ui"
}
```

| Key | |
|---|---|
| `icon` | An SVG shown in the workspace rail with `name` under it. Draw with `stroke="currentColor"` so it follows the rail's colors. |
| `server` | `module:function`. The module is imported with the plugin folder on `sys.path`; `function(ctx)` returns a FastAPI `APIRouter`, mounted at `/api/plugins/<id>`. `ctx.store` is the `Store` (projects, entities, `publish(...)`…), `ctx.data_dir`, `ctx.helpers["blender"]()` (the server's Blender), `ctx.helpers["events"]`. |
| `ui` | A folder of static files served at `/plugins/<id>/`. Its `index.html` is the plugin's workspace (an iframe, with `?project=<id>`). Link `/theme.css` and load `/theme.js` in `<head>` for the app's look and its dark or light theme (use the CSS variables, not fixed colors); call the plugin's routes and the app's API (`/api/...`) with fetch. |

A plugin that fails to load is listed in Settings with its error; it never stops the server. Plugins run with the server's rights: only install plugins you trust.

To publish files from a plugin: `ctx.store.publish(task_id, variant, write=lambda path: ..., ext=".blend", origin="<plugin id>", description=...)` writes the next version and tells every client.
