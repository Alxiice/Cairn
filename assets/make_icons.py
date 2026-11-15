"""Render the bitmap icons from logo-icon-small.svg, cropped to the cairn and dot (view box 22 21 98 98).

tray-icon.png (64 px, system tray), app-icon.png (256 px, window icon on Linux and macOS),
app-icon.ico (16 to 256 px, window and taskbar icon on Windows: WinForms only takes .ico).
Run again after make_logo.py if the logo changes. Needs PySide6 (rendering) and Pillow.
"""
import io
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QBuffer, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

HERE = Path(__file__).parent


def render(size: int) -> Image.Image:
    svg = QSvgRenderer(str(HERE / "logo-icon-small.svg"))
    svg.setViewBox(QRectF(22, 21, 98, 98))
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    svg.render(p)
    p.end()
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


if __name__ == "__main__":
    app = QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
    render(64).save(HERE / "tray-icon.png")
    big = render(256)
    big.save(HERE / "app-icon.png")
    big.save(HERE / "app-icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    ico = Image.open(HERE / "app-icon.ico")
    assert (256, 256) in ico.info["sizes"] and (16, 16) in ico.info["sizes"], ico.info
    print("wrote tray-icon.png, app-icon.png, app-icon.ico")
