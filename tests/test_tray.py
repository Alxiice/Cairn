import socket
import time

from fastapi.testclient import TestClient

from cairn import tray
from cairn.api import create_app


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_serve_and_quit_without_an_icon(tmp_path):
    port = free_port()
    url = tray.url_of("0.0.0.0", port)
    assert url == f"http://127.0.0.1:{port}"
    assert not tray.running(url, timeout=0.3)
    t = tray.TrayServer("127.0.0.1", port, str(tmp_path / "data"), [], "")
    t.serve()
    end = time.time() + 15
    while not tray.running(url) and time.time() < end:
        time.sleep(0.1)
    assert tray.running(url)
    assert not tray.port_free("127.0.0.1", port)
    assert tray.control("127.0.0.1", port, "stop") == 0  # the Stop menu, through the API
    assert t.done.wait(15)
    assert not tray.running(url, timeout=0.3)
    assert tray.port_free("127.0.0.1", port)


def test_control_route_needs_a_tray_server(tmp_path):
    app = create_app(tmp_path, web_dist=None)
    c = TestClient(app)
    assert c.post("/api/server/stop").status_code == 400  # a plain `serve` cannot be stopped remotely
    assert c.post("/api/server/explode").status_code == 422
    calls = []
    app.state.restart_server = lambda: calls.append("restart")
    assert c.post("/api/server/restart").status_code == 200
    assert calls == ["restart"]
    app.state.store.db.close()
