<img src="assets/logo.svg" alt="Cairn" height="64">

**Cairn** is a production tracker and asset manager for small Blender projects. It helps organizing:
- sequences
- shots
- assets

And organize the production around tasks, and manage the production through versionned published files, notes with replies and attachments, and review of renders side by side.

This is aimed to be a tool that helps creators to organize and manage their project go from the start to the end. It integrates a plugin system to help adding specific tools for projects.

## Quick start

Needs Python 3.11+ and Node 20.19+ (only to build the UI). On Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd web; npm install; npm run build; cd ..
```

Then double-click `Cairn.bat` (or run `./cairn.sh` on Linux and macOS): it starts the server in the system tray and opens the app window.

Linux and macOS, all the commands, sharing a project on the network and plugins: see the [documentation](https://alxiice.github.io/Cairn/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md): setup, tech stack, architecture and rules.

## License

Apache-2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE). Dependencies keep their own licenses: all permissive except pystray (LGPL-3.0), which Cairn only imports, unmodified.
