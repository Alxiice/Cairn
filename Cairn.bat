@echo off
rem Starts the Cairn server in the system tray (detached: closing this window does not stop it), then the app window.
cd /d "%~dp0"
py -m cairn start %*
