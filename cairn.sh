#!/bin/sh
# Starts the Cairn server in the system tray (detached: closing the terminal does not stop it), then the app window.
# Uses the project's virtualenv (.venv) when there is one, else python3.
cd "$(dirname "$0")" || exit 1
py=.venv/bin/python
[ -x "$py" ] || py=python3
exec "$py" -m cairn start "$@"
