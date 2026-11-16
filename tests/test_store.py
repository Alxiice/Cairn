from pathlib import Path

import pytest

from cairn.store import NotFound, Store, StoreError


def write(text: str):
    return lambda p: p.write_text(text)


@pytest.fixture
def changes():
    return []


@pytest.fixture
def s(tmp_path, changes):
    store = Store(tmp_path / "db.sqlite", on_change=lambda pid, what: changes.append(what))
    yield store
    store.db.close()


@pytest.fixture
def p(s, tmp_path):
    return s.create_project("Outer Wilds AMV", "amv", str(tmp_path / "amv"))


@pytest.fixture
def tpl(s, p):
    return {t["name"]: t for t in s.templates(p["id"])}


def test_moves_b3dprod_project_data(s, p):
    """Cairn was named B3DProd: a project's .b3dprod folder and the paths stored for it move to .cairn."""
    shot = s.create_entity(p["id"], "shot", "sh010")
    s.set_thumbnail(shot["id"], b"png", ".png")
    root = Path(p["root"])
    (root / ".cairn").rename(root / ".b3dprod")
    s.db.execute("UPDATE entities SET thumbnail = replace(thumbnail, '.cairn/', '.b3dprod/')")
    s.db.close()
    again = Store(s.path)
    try:
        assert again.thumbnail_path(shot["id"]).read_bytes() == b"png"
        assert not (root / ".b3dprod").exists()
    finally:
        again.db.close()


def test_templates_drive_new_entities(s, p, tpl):
    pid = p["id"]
    seq = s.create_sequence(pid, "Rise")
    shot = s.create_entity(pid, "shot", "sh030", sequence_id=seq["id"], title="Quantum Moon orbit")
    assert [t["name"] for t in shot["tasks"]] == ["blocking", "layout", "animation", "rendering", "compositing"]
    planet = s.create_entity(pid, "asset", "timber_hearth", asset_type="set", template_id=tpl["Set"]["id"])
    assert [t["name"] for t in planet["tasks"]] == ["modeling", "surfacing", "lookdev"]  # no rig for a planet
    hero = s.create_entity(pid, "asset", "hatchling", asset_type="character")  # the default asset template
    assert "rig" in [t["name"] for t in hero["tasks"]]
    with pytest.raises(StoreError):
        s.create_entity(pid, "asset", "x", asset_type="set", template_id=tpl["Shot"]["id"])  # wrong kind
    # a new default for assets
    s.update_project(pid, default_asset_template=tpl["Prop"]["id"])
    assert [t["name"] for t in s.create_entity(pid, "asset", "lamp", asset_type="prop")["tasks"]] == ["modeling", "surfacing"]
    with pytest.raises(StoreError):
        s.delete_template(tpl["Prop"]["id"])  # it is a default now


def test_custom_tasks_remove_and_apply_template(s, p, tpl):
    e = s.create_entity(p["id"], "asset", "quantum_moon", asset_type="set", template_id=tpl["Character"]["id"])
    tasks = {t["name"]: t for t in e["tasks"]}
    s.publish(tasks["rig"]["id"], write=write("rig"))  # rig has a version: it can only be disabled
    e = s.add_task(e["id"], "extraction")
    assert next(t for t in e["tasks"] if t["name"] == "extraction")["custom"]
    e = s.remove_task(tasks["modeling"]["id"])
    assert "modeling" not in [t["name"] for t in e["tasks"]]
    e = s.apply_template(e["id"], tpl["Set"]["id"])
    assert [(t["name"], t["enabled"]) for t in e["tasks"]] == [
        ("modeling", True), ("surfacing", True), ("lookdev", True), ("rig", False), ("extraction", True)]
    with pytest.raises(StoreError):
        s.publish(tasks["rig"]["id"], write=write("x"))  # disabled
    e = s.add_task(e["id"], "rig")  # enabling it again keeps its versions
    assert next(t for t in e["tasks"] if t["name"] == "rig")["enabled"]
    with pytest.raises(StoreError):
        s.add_task(e["id"], "rig")


def test_publish_numbers_paths_and_never_overwrites(s, p, changes):
    pid = p["id"]
    e = s.create_entity(pid, "shot", "sh010")
    layout = next(t for t in e["tasks"] if t["name"] == "layout")
    v1 = s.publish(layout["id"], write=write("one"))
    assert v1["path"] == "shots/sh010/layout/base/sh010_layout_base_v001.blend"
    stray = Path(p["root"]) / "shots/sh010/layout/base/sh010_layout_base_v002.blend"
    stray.write_text("made by hand")
    v = s.publish(layout["id"], write=write("two"))
    assert v["number"] == 3
    assert stray.read_text() == "made by hand"
    copy = s.copy_version(layout["id"], "alt", v1["id"])
    assert (copy["variant"], copy["number"], copy["source_id"]) == ("alt", 1, v1["id"])
    assert s.version_path(copy["id"]).read_text() == "one"
    render = s.publish(next(t for t in e["tasks"] if t["name"] == "rendering")["id"], ext="", write=lambda p: p.mkdir())
    assert render["kind"] == "folder"
    # a failed write leaves no record and frees the number
    with pytest.raises(RuntimeError):
        s.publish(layout["id"], write=lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
    assert s.publish(layout["id"], write=write("four"))["number"] == 4
    row = next(r for r in s.entities(pid, "shot") if r["id"] == e["id"])
    row_layout = next(t for t in row["tasks"] if t["name"] == "layout")
    assert (row_layout["latest"], row_layout["status"]) == (4, "wip")
    assert "versions" in changes


def test_uses_and_loops(s, p):
    pid = p["id"]
    shot = s.create_entity(pid, "shot", "sh030")
    moon = s.create_entity(pid, "asset", "quantum_moon", asset_type="set")
    shrine = s.create_entity(pid, "asset", "shrine", asset_type="prop")
    s.add_use(shot["id"], moon["id"])
    s.add_use(moon["id"], shrine["id"])
    with pytest.raises(StoreError):
        s.add_use(shrine["id"], moon["id"])
    with pytest.raises(StoreError):
        s.add_use(moon["id"], shot["id"])  # only assets are used
    e = s.entity(moon["id"])
    assert ([u["name"] for u in e["uses"]], [u["name"] for u in e["used_in"]]) == (["shrine"], ["sh030"])


def test_delete_sequence_and_entities_keeps_files(s, p):
    pid = p["id"]
    seq = s.create_sequence(pid, "Rise")
    shot = s.create_entity(pid, "shot", "sh030", sequence_id=seq["id"])
    moon = s.create_entity(pid, "asset", "quantum_moon", asset_type="set")
    s.add_use(shot["id"], moon["id"])
    task = s.entity(moon["id"])["tasks"][0]["id"]
    v = s.publish(task, "base", ext=".txt", write=write("moon"))
    copy = s.copy_version(s.entity(shot["id"])["tasks"][0]["id"], "base", v["id"])
    s.create_note(pid, "Too dark", links=[{"target": "version", "id": v["id"]}, {"target": "entity", "id": moon["id"]}])
    s.delete_sequence(seq["id"])
    assert s.entity(shot["id"])["sequence_id"] is None
    s.delete_entity(moon["id"])
    with pytest.raises(NotFound):
        s.entity(moon["id"])
    assert s.version_path(copy["id"]).exists()
    assert (Path(p["root"]) / v["path"]).exists()  # never delete a version file
    assert s.entity(shot["id"])["uses"] == []


def test_notes_link_shots_assets_versions_and_tasks(s, p, tmp_path):
    pid = p["id"]
    shot = s.create_entity(pid, "shot", "sh030")
    task = shot["tasks"][3]
    v = s.publish(task["id"], ext=".mp4", write=write("video"))
    n = s.create_note(pid, "Moon jump too early", "frame 148", frame=148,
                      links=[{"target": "entity", "id": shot["id"]}, {"target": "version", "id": v["id"]},
                             {"target": "task", "id": task["id"]}], assignees=[1])
    assert [l["label"] for l in n["links"]] == ["sh030", "sh030 · rendering", "sh030 · rendering · base · v001"]
    s.reply(n["id"], "fixed in layout v005")
    n = s.attach(n["id"], "file", "", "frame.png", data=b"png")
    assert s.attachment_path(n["attachments"][0]["id"]).is_file()
    with pytest.raises(StoreError):
        s.attach(n["id"], "url", "javascript:alert(1)")
    assert len(s.notes(pid, target="version", target_id=v["id"])) == 1
    assert s.entities(pid, "shot")[0]["open_notes"] == 1
    s.update_note(n["id"], status="closed")
    assert s.notes(pid, status="open") == []
    other = s.create_project("Other", "other", str(tmp_path / "o"))
    with pytest.raises(StoreError):
        s.create_note(other["id"], "x", links=[{"target": "entity", "id": shot["id"]}])
    assert [r["type"] for r in s.search(pid, "sh030")][:1] == ["shot"]
    assert any(a["verb"] == "published" for a in s.activity(pid))
    with pytest.raises(NotFound):
        s.note(999)
