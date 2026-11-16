# Installation

Cairn needs **Python 3.11 or newer** (tested on 3.13). Building the web UI also needs **Node 20.19 or newer**.

## Install

Get the code, then install Cairn in a virtualenv named `.venv` in the Cairn folder. The launchers look for it there.

=== "Windows (PowerShell)"

    ```powershell
    git clone https://github.com/Alxiice/Cairn.git
    cd Cairn
    py -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    cd web; npm install; npm run build; cd ..
    ```

=== "Linux, macOS"

    ```sh
    git clone https://github.com/Alxiice/Cairn.git
    cd Cairn
    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install -r requirements.txt
    (cd web && npm install && npm run build)
    ```

The `python -m cairn` commands in this documentation run in the activated virtualenv.

## Start

Double-click **`Cairn.bat`** (Windows) or run **`./cairn.sh`** (Linux, macOS). The launchers use `.venv` by themselves, so there is no need to activate it.

The launcher starts the Cairn server **in the system tray** and opens the app window. The server runs on its own: closing the terminal or the app window leaves it running. Run the launcher again and it reuses the running server and opens another window. To stop the server, use **Stop** in the tray menu or `python -m cairn stop`.

!!! note "Linux"
    The tray icon needs a system tray. On GNOME, install the AppIndicator extension (and `gir1.2-ayatanaappindicator3-0.1` or similar); other desktops have an X11 tray. Without one, the server still runs, without an icon.

    The app window needs GTK and WebKitGTK, or Qt, from your distribution.

## Blender

On Windows, Cairn finds the newest Blender installed in `C:\Program Files\Blender Foundation`. Elsewhere, or to use another one, set `blender` in `~/.cairn/settings.json` to the Blender executable, or pass `--blender <path>`.
