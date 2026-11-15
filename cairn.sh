#!/bin/sh
# Starts the Cairn server in the system tray (detached: closing the terminal does not stop it), then the app window.
cd "$(dirname "$0")" && exec python3 -m cairn start "$@"
