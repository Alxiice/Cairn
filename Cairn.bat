@echo off
rem Starts the Cairn server in the system tray (detached: closing this window does not stop it), then the app window.
rem Uses the project's virtualenv (.venv) when there is one, else the Python launcher.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m cairn start %*
) else (
  py -m cairn start %*
)
