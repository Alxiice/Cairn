import json

import pytest
from fastapi.testclient import TestClient

from cairn.api import create_app

PLUGIN = '''
from fastapi import APIRouter

def register(ctx):
    r = APIRouter()
    @r.get("/status")
    def status():
        return {"projects": len(ctx.store.projects())}
    return r
'''


@pytest.fixture
def plugins(tmp_path):
    """A plugin folder with a working plugin (fake) and one that fails to load (broken)."""
    plug = tmp_path / "plugins" / "fake"
    (plug / "ui").mkdir(parents=True)
    (plug / "plugin.json").write_text(json.dumps({"id": "fake", "name": "FAKE", "icon": "icon.svg",
                                                  "server": "fake_server:register", "ui": "ui"}))
    (plug / "icon.svg").write_text('<svg viewBox="0 0 24 24"></svg>')
    (plug / "fake_server.py").write_text(PLUGIN)
    (plug / "ui" / "index.html").write_text("<p>fake</p>")
    broken = tmp_path / "plugins" / "broken"
    broken.mkdir()
    (broken / "plugin.json").write_text('{"id": "broken", "server": "nope:register"}')
    return tmp_path / "plugins"


@pytest.fixture
def c(tmp_path, plugins):
    app = create_app(tmp_path / "data", [str(plugins)], web_dist=None)
    yield TestClient(app)
    app.state.store.db.close()


def ok(c, method, url, **kw):
    r = c.request(method, url, **kw)
    assert r.status_code < 300, r.text
    return r.json()


def test_production_flow(c):
    p = ok(c, "POST", "/api/projects", json={"name": "AMV", "code": "amv"})
    pid = p["id"]
    assert p["root"].endswith("amv")
    seq = ok(c, "POST", f"/api/projects/{pid}/sequences", json={"name": "Rise"})
    set_tpl = next(t for t in ok(c, "GET", f"/api/projects/{pid}/templates") if t["name"] == "Set")
    shot = ok(c, "POST", f"/api/projects/{pid}/entities", json={"kind": "shot", "name": "sh030", "sequence_id": seq["id"]})
    moon = ok(c, "POST", f"/api/projects/{pid}/entities",
              json={"kind": "asset", "name": "quantum_moon", "asset_type": "set", "template_id": set_tpl["id"]})
    ok(c, "POST", f"/api/entities/{shot['id']}/uses", json={"child_id": moon["id"]})
    e = ok(c, "PATCH", f"/api/entities/{shot['id']}", json={"cut_in": 9, "cut_out": 232, "title": "Orbit"})
    assert (e["cut_in"], e["title"], e["uses"][0]["name"]) == (9, "Orbit", "quantum_moon")
    bad = c.patch(f"/api/entities/{shot['id']}", json={"cut_out": 999})
    assert bad.status_code == 400
    assert "head" in bad.json()["detail"]

    render = next(t for t in e["tasks"] if t["name"] == "rendering")
    v = ok(c, "POST", f"/api/entities/{shot['id']}/versions/upload", data={"task_id": render["id"], "variant": "previz"},
           files={"file": ("color.mp4", b"\x00mp4data", "video/mp4")})
    assert v["path"] == "shots/sh030/rendering/previz/sh030_rendering_previz_v001.mp4"
    r = c.get(f"/api/versions/{v['id']}/file")
    assert (r.status_code, r.content, r.headers["content-type"]) == (200, b"\x00mp4data", "video/mp4")
    copy = ok(c, "POST", f"/api/entities/{shot['id']}/versions",
              json={"task_id": render["id"], "variant": "previz", "mode": "copy", "source_id": v["id"], "uses": []})
    assert copy["number"] == 2
    other_task = moon["tasks"][0]["id"]
    assert c.post(f"/api/entities/{shot['id']}/versions",
                  json={"task_id": other_task, "mode": "copy", "source_id": v["id"]}).status_code == 400

    n = ok(c, "POST", f"/api/projects/{pid}/notes",
           json={"title": "Jump too early", "links": [{"target": "version", "id": v["id"]}, {"target": "entity", "id": shot["id"]}]})
    ok(c, "POST", f"/api/notes/{n['id']}/replies", json={"content": "fixed"})
    n = ok(c, "POST", f"/api/notes/{n['id']}/attachments", files={"file": ("f.png", b"png", "image/png")})
    assert c.get(f"/api/attachments/{n['attachments'][0]['id']}").content == b"png"
    rows = ok(c, "GET", f"/api/projects/{pid}/entities?kind=shot")
    assert (rows[0]["open_notes"], rows[0]["sequence"]) == (1, "Rise")
    assert ok(c, "GET", f"/api/projects/{pid}/notes?target=version&target_id={v['id']}")[0]["title"] == "Jump too early"
    assert ok(c, "GET", f"/api/projects/{pid}/search?q=quantum")
    assert ok(c, "GET", f"/api/projects/{pid}/activity")
    ok(c, "POST", f"/api/entities/{moon['id']}/thumbnail", files={"file": ("t.png", b"img", "image/png")})
    assert c.get(f"/api/entities/{moon['id']}/thumbnail").content == b"img"
    assert c.post(f"/api/entities/{moon['id']}/thumbnail", files={"file": ("t.exe", b"x")}).status_code == 400
    assert c.get("/api/entities/9999").status_code == 404


def test_plugins(c):
    plugins = {p["id"]: p for p in ok(c, "GET", "/api/plugins")}
    assert plugins["fake"]["name"] == "FAKE"
    assert "<svg" in plugins["fake"]["icon"]
    assert plugins["fake"]["ui"] == "/plugins/fake/"
    assert plugins["broken"]["error"]
    assert ok(c, "GET", "/api/plugins/fake/status") == {"projects": 0}
    assert "fake" in c.get("/plugins/fake/").text


def test_plugin_folders_from_settings(tmp_path, plugins):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<p>app</p>")
    (tmp_path / "data").mkdir()
    app = create_app(tmp_path / "data2", [], web_dist=dist)  # the web UI at "/" must not hide plugins added later
    c = TestClient(app)
    assert c.get("/api/plugins").json() == []
    assert c.post("/api/plugin-folders", json={"path": str(tmp_path / "nope")}).status_code == 400
    assert c.post("/api/plugin-folders", json={"path": str(tmp_path / "data")}).status_code == 400  # no plugin.json
    r = c.post("/api/plugin-folders", json={"path": str(plugins)})
    assert r.status_code == 200, r.text
    assert sorted(p["id"] for p in r.json()["loaded"]) == ["broken", "fake"]
    assert "fake" in [p["id"] for p in c.get("/api/plugins").json()]
    assert c.get("/api/plugins/fake/status").json() == {"projects": 0}  # served at once, not hidden by "/"
    assert "fake" in c.get("/plugins/fake/").text
    assert "app" in c.get("/").text
    folders = c.get("/api/plugin-folders").json()
    assert (folders[0]["source"], sorted(folders[0]["plugins"])) == ("added", ["broken", "fake"])
    # saved: a new server on the same data loads it again
    app.state.store.db.close()
    again = TestClient(create_app(tmp_path / "data2", [], web_dist=None))
    assert "fake" in [p["id"] for p in again.get("/api/plugins").json()]
    r = again.delete("/api/plugin-folders", params={"path": folders[0]["path"]})
    assert (r.status_code, r.json()["restart"], r.json()["folders"]) == (200, True, [])
    again.app.state.store.db.close()
