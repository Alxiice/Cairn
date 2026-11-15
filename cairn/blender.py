"""Finding and running Blender."""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
from pathlib import Path


class BlenderError(Exception):
    pass


def find_blender(configured: str | None = None) -> Path | None:
    """The configured executable if it exists, else the newest standard Windows install."""
    if configured and Path(configured).is_file():
        return Path(configured)
    candidates = glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe")

    def version(p: str) -> tuple:
        m = re.search(r"Blender (\d+)\.(\d+)", p)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    candidates.sort(key=version)
    return Path(candidates[-1]) if candidates else None


def open_in_blender(exe: Path, blend: Path) -> None:
    """Starts Blender on a file, detached: closing Cairn leaves Blender open."""
    if not blend.is_file():
        raise BlenderError(f"{blend} not found")
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(exe), str(blend)], cwd=str(blend.parent), creationflags=flags, close_fds=True)


def create_empty(exe: Path, blend: Path, timeout: float = 180) -> None:
    """Saves Blender's factory startup scene as a new file (background process, blocking)."""
    if blend.exists():
        raise BlenderError(f"{blend.name} already exists")
    blend.parent.mkdir(parents=True, exist_ok=True)
    script = f"import bpy; bpy.ops.wm.save_as_mainfile(filepath={str(blend)!r}, check_existing=False)"
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    result = subprocess.run([str(exe), "-b", "--factory-startup", "--python-expr", script],
                            capture_output=True, text=True, timeout=timeout, creationflags=flags)
    if result.returncode != 0 or not blend.is_file():
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
        raise BlenderError("Blender could not create the file: " + " / ".join(tail))


def open_folder(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(folder))  # noqa: S606 - opens Explorer on a folder we own
    else:
        subprocess.Popen(["xdg-open", str(folder)])
