"""The production database: projects, sequences, shots and assets (entities), task templates, tasks, versions
(published files), notes with replies and attachments, activity. SQLite, no HTTP and no UI here, so it is tested
directly and the API (api.py) stays thin.

Files: each project has a root folder on the server machine. Versions are files under it, never overwritten:
  shots/<shot>/<task>/<variant>/<shot>_<task>_<variant>_v001.<ext>
  assets/<type>/<asset>/<task>/<variant>/<asset>_<task>_<variant>_v001.<ext>
(the layout of Cairn 0.3, so its Blender add-on still recognises the files).
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

STATUSES = ["ns", "wip", "rev", "ret", "app", "skip"]  # not started, WIP, review, retake, approved, skipped
KINDS = ("shot", "asset")
NAME_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
THUMB_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_TEMPLATES = [
    ("Shot", "shot", ["blocking", "layout", "animation", "rendering", "compositing"]),
    ("Character", "asset", ["modeling", "rig", "surfacing", "lookdev"]),
    ("Set", "asset", ["modeling", "surfacing", "lookdev"]),
    ("Prop", "asset", ["modeling", "surfacing"]),
]

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, occupation TEXT NOT NULL DEFAULT '', created_at TEXT);
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '',
  fps INTEGER NOT NULL DEFAULT 24, width INTEGER NOT NULL DEFAULT 1920, height INTEGER NOT NULL DEFAULT 1080,
  root TEXT NOT NULL, asset_types TEXT NOT NULL DEFAULT '["character","set","prop","fx"]',
  default_shot_template INTEGER, default_asset_template INTEGER, created_at TEXT, created_by INTEGER);
CREATE TABLE IF NOT EXISTS sequences(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', sort INTEGER NOT NULL DEFAULT 0, UNIQUE(project_id, name));
CREATE TABLE IF NOT EXISTS templates(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('shot','asset')), tasks TEXT NOT NULL DEFAULT '[]',
  UNIQUE(project_id, name));
CREATE TABLE IF NOT EXISTS entities(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('shot','asset')), name TEXT NOT NULL, title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '', sequence_id INTEGER REFERENCES sequences(id) ON DELETE SET NULL,
  asset_type TEXT NOT NULL DEFAULT '', head INTEGER, tail INTEGER, cut_in INTEGER, cut_out INTEGER,
  thumbnail TEXT NOT NULL DEFAULT '', created_at TEXT, created_by INTEGER, updated_at TEXT, updated_by INTEGER,
  UNIQUE(project_id, name));
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY, entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ns', assignee_id INTEGER REFERENCES users(id),
  sort INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1, custom INTEGER NOT NULL DEFAULT 0,
  UNIQUE(entity_id, name));
CREATE TABLE IF NOT EXISTS uses(
  parent_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  child_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE, PRIMARY KEY(parent_id, child_id));
CREATE TABLE IF NOT EXISTS versions(
  id INTEGER PRIMARY KEY, entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  task_id INTEGER NOT NULL REFERENCES tasks(id), variant TEXT NOT NULL DEFAULT 'base', number INTEGER NOT NULL,
  kind TEXT NOT NULL, path TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', origin TEXT NOT NULL DEFAULT 'cairn',
  source_id INTEGER REFERENCES versions(id), thumbnail TEXT NOT NULL DEFAULT '', created_at TEXT, created_by INTEGER,
  UNIQUE(task_id, variant, number));
CREATE TABLE IF NOT EXISTS version_uses(
  version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
  used_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE, PRIMARY KEY(version_id, used_id));
CREATE TABLE IF NOT EXISTS notes(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open',
  frame INTEGER, created_at TEXT, created_by INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS note_links(
  note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  target TEXT NOT NULL CHECK(target IN ('entity','version','task')), target_id INTEGER NOT NULL,
  PRIMARY KEY(note_id, target, target_id));
CREATE TABLE IF NOT EXISTS note_assignees(
  note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE, user_id INTEGER NOT NULL REFERENCES users(id),
  PRIMARY KEY(note_id, user_id));
CREATE TABLE IF NOT EXISTS replies(
  id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  content TEXT NOT NULL, created_at TEXT, created_by INTEGER);
CREATE TABLE IF NOT EXISTS attachments(
  id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  reply_id INTEGER REFERENCES replies(id) ON DELETE CASCADE, kind TEXT NOT NULL CHECK(kind IN ('url','file')),
  value TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', created_at TEXT, created_by INTEGER);
CREATE TABLE IF NOT EXISTS activity(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  at TEXT, user_id INTEGER, verb TEXT NOT NULL, label TEXT NOT NULL, target TEXT, target_id INTEGER);
CREATE INDEX IF NOT EXISTS ix_entities_project ON entities(project_id, kind);
CREATE INDEX IF NOT EXISTS ix_tasks_entity ON tasks(entity_id);
CREATE INDEX IF NOT EXISTS ix_versions_entity ON versions(entity_id);
CREATE INDEX IF NOT EXISTS ix_note_links_target ON note_links(target, target_id);
"""


class StoreError(Exception):
    """A request that cannot be done (bad name, missing item, conflict). Shown to the user as is."""


class NotFound(StoreError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_name(name: str, what: str = "name") -> str:
    if not NAME_RE.match(name or ""):
        raise StoreError(f"{what} '{name}' must be lower_snake_case: a-z, 0-9 and single underscores")
    return name


def _row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None


class Store:
    """Thread-safe: one connection, one lock (FastAPI runs sync endpoints on a thread pool)."""

    def __init__(self, db_path: Path | str, on_change: Callable[[int | None, str], None] | None = None):
        self.path = str(db_path)
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()
        self.on_change = on_change or (lambda project_id, what: None)
        if not self.db.execute("SELECT 1 FROM users").fetchone():
            self.db.execute("INSERT INTO users(name, occupation, created_at) VALUES ('You', '', ?)", (now(),))
        self._migrate_from_b3dprod()

    def _migrate_from_b3dprod(self) -> None:
        """Cairn was named B3DProd: moves each project's .b3dprod folder to .cairn and fixes the paths stored for it."""
        with self.tx() as db:
            db.execute("UPDATE versions SET origin = 'cairn' WHERE origin = 'b3dprod'")
            for p in db.execute("SELECT id, root FROM projects").fetchall():
                old, new = Path(p["root"]) / ".b3dprod", Path(p["root"]) / ".cairn"
                if old.is_dir() and not new.exists():
                    old.rename(new)
                if old.exists():
                    continue  # both folders exist: leave it to the user rather than mix them
                db.execute("UPDATE entities SET thumbnail = '.cairn' || substr(thumbnail, 9) "
                           "WHERE project_id = ? AND thumbnail LIKE '.b3dprod/%'", (p["id"],))
                db.execute("UPDATE attachments SET value = '.cairn' || substr(value, 9) WHERE kind = 'file' "
                           "AND value LIKE '.b3dprod/%' AND note_id IN (SELECT id FROM notes WHERE project_id = ?)", (p["id"],))

    # ---------- helpers ----------

    def q(self, sql: str, args=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def one(self, sql: str, args=(), what: str = "item") -> dict:
        with self.lock:
            r = _row(self.db.execute(sql, args).fetchone())
        if r is None:
            raise NotFound(f"No such {what}")
        return r

    def tx(self):
        """`with store.tx():` runs the block in one transaction, under the lock."""
        store = self

        class _Tx:
            def __enter__(self):
                store.lock.acquire()
                store.db.execute("BEGIN IMMEDIATE")
                return store.db

            def __exit__(self, exc_type, exc, tb):
                try:
                    store.db.execute("ROLLBACK" if exc_type else "COMMIT")
                finally:
                    store.lock.release()
                return False
        return _Tx()

    def _log(self, db, project_id: int, user: int, verb: str, label: str, target: str = "", target_id: int | None = None):
        db.execute("INSERT INTO activity(project_id, at, user_id, verb, label, target, target_id) VALUES (?,?,?,?,?,?,?)",
                   (project_id, now(), user, verb, label, target, target_id))

    def _changed(self, project_id: int | None, what: str):
        self.on_change(project_id, what)

    # ---------- users ----------

    def users(self) -> list[dict]:
        return self.q("SELECT id, name, occupation FROM users ORDER BY id")

    # ---------- projects ----------

    def projects(self) -> list[dict]:
        return [self._project_out(p) for p in self.q("SELECT * FROM projects ORDER BY name")]

    def project(self, pid: int) -> dict:
        return self._project_out(self.one("SELECT * FROM projects WHERE id = ?", (pid,), "project"))

    @staticmethod
    def _project_out(p: dict) -> dict:
        p["asset_types"] = json.loads(p["asset_types"])
        return p

    def create_project(self, name: str, code: str, root: str, user: int = 1, fps: int = 24,
                       width: int = 1920, height: int = 1080, description: str = "") -> dict:
        check_name(code, "project code")
        if not name.strip():
            raise StoreError("A project needs a name")
        Path(root).mkdir(parents=True, exist_ok=True)
        with self.tx() as db:
            if db.execute("SELECT 1 FROM projects WHERE code = ?", (code,)).fetchone():
                raise StoreError(f"A project with code {code} exists")
            pid = db.execute("INSERT INTO projects(name, code, description, fps, width, height, root, created_at, created_by) "
                             "VALUES (?,?,?,?,?,?,?,?,?)", (name.strip(), code, description, fps, width, height,
                                                           str(Path(root).resolve()), now(), user)).lastrowid
            ids = {}
            for tname, kind, tasks in DEFAULT_TEMPLATES:
                ids[tname] = db.execute("INSERT INTO templates(project_id, name, kind, tasks) VALUES (?,?,?,?)",
                                        (pid, tname, kind, json.dumps(tasks))).lastrowid
            db.execute("UPDATE projects SET default_shot_template = ?, default_asset_template = ? WHERE id = ?",
                       (ids["Shot"], ids["Character"], pid))
            self._log(db, pid, user, "created", f"project {name.strip()}", "project", pid)
        self._changed(None, "projects")
        return self.project(pid)

    def update_project(self, pid: int, user: int = 1, **f) -> dict:
        allowed = {"name", "description", "fps", "width", "height", "asset_types", "default_shot_template", "default_asset_template"}
        f = {k: v for k, v in f.items() if v is not None}
        bad = set(f) - allowed
        if bad:
            raise StoreError(f"Unknown project field {', '.join(sorted(bad))}")
        if "asset_types" in f:
            f["asset_types"] = json.dumps([check_name(t, "asset type") for t in f["asset_types"]])
        for key, kind in (("default_shot_template", "shot"), ("default_asset_template", "asset")):
            if key in f:
                self._template_of_kind(pid, f[key], kind)
        with self.tx() as db:
            self.one("SELECT id FROM projects WHERE id = ?", (pid,), "project")
            for k, v in f.items():
                db.execute(f"UPDATE projects SET {k} = ? WHERE id = ?", (v, pid))  # k is from the allow-list
        self._changed(pid, "project")
        return self.project(pid)

    # ---------- sequences ----------

    def sequences(self, pid: int) -> list[dict]:
        return self.q("SELECT s.*, (SELECT COUNT(*) FROM entities e WHERE e.sequence_id = s.id) AS shot_count "
                      "FROM sequences s WHERE project_id = ? ORDER BY sort, name", (pid,))

    def create_sequence(self, pid: int, name: str, description: str = "", user: int = 1) -> dict:
        if not name.strip():
            raise StoreError("A sequence needs a name")
        with self.tx() as db:
            if db.execute("SELECT 1 FROM sequences WHERE project_id = ? AND name = ?", (pid, name.strip())).fetchone():
                raise StoreError(f"Sequence {name} exists")
            sort = db.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM sequences WHERE project_id = ?", (pid,)).fetchone()[0]
            sid = db.execute("INSERT INTO sequences(project_id, name, description, sort) VALUES (?,?,?,?)",
                             (pid, name.strip(), description, sort)).lastrowid
            self._log(db, pid, user, "created", f"sequence {name.strip()}", "sequence", sid)
        self._changed(pid, "sequences")
        return self.one("SELECT * FROM sequences WHERE id = ?", (sid,))

    def update_sequence(self, sid: int, name: str | None = None, description: str | None = None, sort: int | None = None) -> dict:
        s = self.one("SELECT * FROM sequences WHERE id = ?", (sid,), "sequence")
        with self.tx() as db:
            db.execute("UPDATE sequences SET name = ?, description = ?, sort = ? WHERE id = ?",
                       ((name or s["name"]).strip(), s["description"] if description is None else description,
                        s["sort"] if sort is None else sort, sid))
        self._changed(s["project_id"], "sequences")
        return self.one("SELECT * FROM sequences WHERE id = ?", (sid,))

    def delete_sequence(self, sid: int, user: int = 1) -> None:
        """Its shots stay, without a sequence (the foreign key sets it to NULL)."""
        s = self.one("SELECT * FROM sequences WHERE id = ?", (sid,), "sequence")
        with self.tx() as db:
            db.execute("DELETE FROM sequences WHERE id = ?", (sid,))
            self._log(db, s["project_id"], user, "deleted", f"sequence {s['name']}", "sequence", sid)
        self._changed(s["project_id"], "sequences")
        self._changed(s["project_id"], "entities")

    # ---------- task templates ----------

    def templates(self, pid: int) -> list[dict]:
        out = self.q("SELECT * FROM templates WHERE project_id = ? ORDER BY kind DESC, name", (pid,))
        for t in out:
            t["tasks"] = json.loads(t["tasks"])
        return out

    def _template_of_kind(self, pid: int, tid: int, kind: str) -> dict:
        t = self.one("SELECT * FROM templates WHERE id = ? AND project_id = ?", (tid, pid), "task template")
        if t["kind"] != kind:
            raise StoreError(f"Template {t['name']} is for {t['kind']}s, not {kind}s")
        t["tasks"] = json.loads(t["tasks"])
        return t

    def save_template(self, pid: int, name: str, kind: str, tasks: list[str], tid: int | None = None) -> dict:
        if kind not in KINDS:
            raise StoreError(f"Unknown kind {kind}")
        if not name.strip():
            raise StoreError("A template needs a name")
        tasks = [check_name(t, "task") for t in tasks]
        if len(set(tasks)) != len(tasks):
            raise StoreError("A template lists each task once")
        with self.tx() as db:
            clash = db.execute("SELECT id FROM templates WHERE project_id = ? AND name = ?", (pid, name.strip())).fetchone()
            if clash and clash[0] != tid:
                raise StoreError(f"Template {name} exists")
            if tid is None:
                tid = db.execute("INSERT INTO templates(project_id, name, kind, tasks) VALUES (?,?,?,?)",
                                 (pid, name.strip(), kind, json.dumps(tasks))).lastrowid
            else:
                old = db.execute("SELECT kind FROM templates WHERE id = ? AND project_id = ?", (tid, pid)).fetchone()
                if not old:
                    raise NotFound("No such task template")
                if old[0] != kind:
                    raise StoreError("A template keeps its kind (shot or asset)")
                db.execute("UPDATE templates SET name = ?, tasks = ? WHERE id = ?", (name.strip(), json.dumps(tasks), tid))
        self._changed(pid, "templates")
        return self._template_of_kind(pid, tid, kind)

    def delete_template(self, tid: int) -> None:
        t = self.one("SELECT * FROM templates WHERE id = ?", (tid,), "task template")
        p = self.one("SELECT * FROM projects WHERE id = ?", (t["project_id"],))
        if tid in (p["default_shot_template"], p["default_asset_template"]):
            raise StoreError("This template is a project default: pick another default first")
        with self.tx() as db:
            db.execute("DELETE FROM templates WHERE id = ?", (tid,))
        self._changed(t["project_id"], "templates")

    # ---------- entities (shots and assets) ----------

    def create_entity(self, pid: int, kind: str, name: str, user: int = 1, template_id: int | None = None,
                      title: str = "", description: str = "", sequence_id: int | None = None, asset_type: str = "",
                      head: int | None = None, tail: int | None = None) -> dict:
        if kind not in KINDS:
            raise StoreError(f"Unknown kind {kind}")
        check_name(name, kind)
        p = self.project(pid)
        if kind == "asset":
            if asset_type not in p["asset_types"]:
                raise StoreError(f"Unknown asset type {asset_type}: the project has {', '.join(p['asset_types'])}")
            sequence_id = None
        else:
            asset_type = ""
            if sequence_id is not None:
                self.one("SELECT id FROM sequences WHERE id = ? AND project_id = ?", (sequence_id, pid), "sequence")
            head, tail = head or 1, tail or 240
            if head > tail:
                raise StoreError("Head must come before tail")
        tid = template_id or p[f"default_{kind}_template"]
        tasks = self._template_of_kind(pid, tid, kind)["tasks"] if tid else []
        with self.tx() as db:
            if db.execute("SELECT 1 FROM entities WHERE project_id = ? AND name = ?", (pid, name)).fetchone():
                raise StoreError(f"{name} exists in this project")
            eid = db.execute(
                "INSERT INTO entities(project_id, kind, name, title, description, sequence_id, asset_type, head, tail, "
                "cut_in, cut_out, created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pid, kind, name, title, description, sequence_id, asset_type, head, tail, head, tail, now(), user, now(), user)).lastrowid
            for i, t in enumerate(tasks):
                db.execute("INSERT INTO tasks(entity_id, name, sort) VALUES (?,?,?)", (eid, t, i))
            self._log(db, pid, user, "created", f"{kind} {name}", "entity", eid)
        self._changed(pid, "entities")
        return self.entity(eid)

    def update_entity(self, eid: int, user: int = 1, **f) -> dict:
        e = self.one("SELECT * FROM entities WHERE id = ?", (eid,), "shot or asset")
        common = {"title", "description"}
        allowed = common | ({"sequence_id", "head", "tail", "cut_in", "cut_out"} if e["kind"] == "shot" else {"asset_type"})
        f = {k: v for k, v in f.items() if v is not None or k == "sequence_id"}
        bad = set(f) - allowed
        if bad:
            raise StoreError(f"A {e['kind']} has no field {', '.join(sorted(bad))}")
        merged = {**e, **f}
        if e["kind"] == "shot":
            if not merged["head"] <= merged["cut_in"] <= merged["cut_out"] <= merged["tail"]:
                raise StoreError("Frames must be head ≤ cut in ≤ cut out ≤ tail")
            if f.get("sequence_id") is not None:
                self.one("SELECT id FROM sequences WHERE id = ? AND project_id = ?", (f["sequence_id"], e["project_id"]), "sequence")
        elif "asset_type" in f and f["asset_type"] not in self.project(e["project_id"])["asset_types"]:
            raise StoreError(f"Unknown asset type {f['asset_type']}")
        with self.tx() as db:
            for k, v in f.items():
                db.execute(f"UPDATE entities SET {k} = ? WHERE id = ?", (v, eid))  # k is from the allow-list
            db.execute("UPDATE entities SET updated_at = ?, updated_by = ? WHERE id = ?", (now(), user, eid))
        self._changed(e["project_id"], "entities")
        return self.entity(eid)

    def delete_entity(self, eid: int, user: int = 1) -> None:
        """Removes a shot or asset and its records (tasks, versions, casting, note links). Files on disk are kept:
        versions are never deleted, so publishing again under the same name skips the numbers already taken."""
        e = self.one("SELECT * FROM entities WHERE id = ?", (eid,), "shot or asset")
        with self.tx() as db:
            vids = "SELECT id FROM versions WHERE entity_id = ?"
            db.execute(f"UPDATE versions SET source_id = NULL WHERE source_id IN ({vids})", (eid,))
            db.execute(f"DELETE FROM note_links WHERE target = 'version' AND target_id IN ({vids})", (eid,))
            db.execute("DELETE FROM note_links WHERE target = 'task' AND target_id IN "
                       "(SELECT id FROM tasks WHERE entity_id = ?)", (eid,))
            db.execute("DELETE FROM note_links WHERE target = 'entity' AND target_id = ?", (eid,))
            db.execute("DELETE FROM versions WHERE entity_id = ?", (eid,))  # before tasks: versions reference them
            db.execute("DELETE FROM entities WHERE id = ?", (eid,))
            self._log(db, e["project_id"], user, "deleted", f"{e['kind']} {e['name']}", "entity", eid)
        self._changed(e["project_id"], "entities")

    def entities(self, pid: int, kind: str | None = None) -> list[dict]:
        """List rows for the tables and grids: tasks with their latest version, counts of notes and uses."""
        args = [pid] + ([kind] if kind else [])
        rows = self.q("SELECT e.*, s.name AS sequence FROM entities e LEFT JOIN sequences s ON s.id = e.sequence_id "
                      "WHERE e.project_id = ?" + (" AND e.kind = ?" if kind else "") +
                      " ORDER BY COALESCE(s.sort, 1e9), e.name", args)
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        marks = ",".join("?" * len(ids))
        tasks = self.q(f"SELECT t.*, (SELECT MAX(number) FROM versions v WHERE v.task_id = t.id) AS latest "
                       f"FROM tasks t WHERE entity_id IN ({marks}) ORDER BY sort, id", ids)
        by_entity: dict[int, list] = {}
        for t in tasks:
            by_entity.setdefault(t["entity_id"], []).append(t)
        notes = dict((r["target_id"], r["n"]) for r in self.q(
            f"SELECT l.target_id, COUNT(*) AS n FROM note_links l JOIN notes n ON n.id = l.note_id "
            f"WHERE l.target = 'entity' AND n.status = 'open' AND l.target_id IN ({marks}) GROUP BY l.target_id", ids))
        used_in = dict((r["child_id"], r["n"]) for r in self.q(
            f"SELECT child_id, COUNT(*) AS n FROM uses WHERE child_id IN ({marks}) GROUP BY child_id", ids))
        uses = dict((r["parent_id"], r["n"]) for r in self.q(
            f"SELECT parent_id, COUNT(*) AS n FROM uses WHERE parent_id IN ({marks}) GROUP BY parent_id", ids))
        versions = dict((r["entity_id"], r["n"]) for r in self.q(
            f"SELECT entity_id, COUNT(*) AS n FROM versions WHERE entity_id IN ({marks}) GROUP BY entity_id", ids))
        for r in rows:
            r["tasks"] = [{"id": t["id"], "name": t["name"], "status": t["status"], "enabled": bool(t["enabled"]),
                           "latest": t["latest"], "assignee_id": t["assignee_id"]} for t in by_entity.get(r["id"], [])]
            r["open_notes"] = notes.get(r["id"], 0)
            r["used_in"] = used_in.get(r["id"], 0)
            r["uses"] = uses.get(r["id"], 0)
            r["version_count"] = versions.get(r["id"], 0)
        return rows

    def entity(self, eid: int) -> dict:
        e = self.one("SELECT e.*, s.name AS sequence FROM entities e LEFT JOIN sequences s ON s.id = e.sequence_id "
                     "WHERE e.id = ?", (eid,), "shot or asset")
        e["tasks"] = self.q("SELECT t.*, (SELECT MAX(number) FROM versions v WHERE v.task_id = t.id) AS latest, "
                            "(SELECT COUNT(*) FROM versions v WHERE v.task_id = t.id) AS version_count "
                            "FROM tasks t WHERE entity_id = ? ORDER BY sort, id", (eid,))
        for t in e["tasks"]:
            t["enabled"] = bool(t["enabled"])
            t["custom"] = bool(t["custom"])
        e["uses"] = self.q("SELECT e.id, e.kind, e.name, e.asset_type FROM uses u JOIN entities e ON e.id = u.child_id "
                           "WHERE u.parent_id = ? ORDER BY e.name", (eid,))
        e["used_in"] = self.q("SELECT e.id, e.kind, e.name, e.asset_type FROM uses u JOIN entities e ON e.id = u.parent_id "
                              "WHERE u.child_id = ? ORDER BY e.kind DESC, e.name", (eid,))
        return e

    # ---------- tasks ----------

    def add_task(self, eid: int, name: str, user: int = 1) -> dict:
        e = self.one("SELECT * FROM entities WHERE id = ?", (eid,), "shot or asset")
        check_name(name, "task")
        with self.tx() as db:
            old = db.execute("SELECT id, enabled FROM tasks WHERE entity_id = ? AND name = ?", (eid, name)).fetchone()
            if old and old["enabled"]:
                raise StoreError(f"{e['name']} already has a {name} task")
            if old:
                db.execute("UPDATE tasks SET enabled = 1 WHERE id = ?", (old["id"],))
            else:
                sort = db.execute("SELECT COALESCE(MAX(sort), -1) + 1 FROM tasks WHERE entity_id = ?", (eid,)).fetchone()[0]
                db.execute("INSERT INTO tasks(entity_id, name, sort, custom) VALUES (?,?,?,1)", (eid, name, sort))
            self._log(db, e["project_id"], user, "added", f"task {name} to {e['name']}", "entity", eid)
        self._changed(e["project_id"], "entities")
        return self.entity(eid)

    def update_task(self, task_id: int, user: int = 1, status: str | None = None, assignee_id: int | None = None,
                    sort: int | None = None, enabled: bool | None = None) -> dict:
        t = self.one("SELECT t.*, e.project_id, e.name AS entity FROM tasks t JOIN entities e ON e.id = t.entity_id "
                     "WHERE t.id = ?", (task_id,), "task")
        if status is not None and status not in STATUSES:
            raise StoreError(f"Unknown status {status}")
        with self.tx() as db:
            if status is not None and status != t["status"]:
                db.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
                self._log(db, t["project_id"], user, "set", f"{t['entity']} {t['name']} to {status}", "entity", t["entity_id"])
            if assignee_id is not None:
                db.execute("UPDATE tasks SET assignee_id = ? WHERE id = ?", (assignee_id or None, task_id))
            if sort is not None:
                db.execute("UPDATE tasks SET sort = ? WHERE id = ?", (sort, task_id))
            if enabled is not None:
                db.execute("UPDATE tasks SET enabled = ? WHERE id = ?", (int(enabled), task_id))
        self._changed(t["project_id"], "entities")
        return self.entity(t["entity_id"])

    def remove_task(self, task_id: int, user: int = 1) -> dict:
        """Deletes a task with no version; a task with versions is disabled instead (history is kept)."""
        t = self.one("SELECT t.*, e.project_id, e.name AS entity FROM tasks t JOIN entities e ON e.id = t.entity_id "
                     "WHERE t.id = ?", (task_id,), "task")
        with self.tx() as db:
            if db.execute("SELECT 1 FROM versions WHERE task_id = ?", (task_id,)).fetchone():
                db.execute("UPDATE tasks SET enabled = 0 WHERE id = ?", (task_id,))
            else:
                db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self._log(db, t["project_id"], user, "removed", f"task {t['name']} from {t['entity']}", "entity", t["entity_id"])
        self._changed(t["project_id"], "entities")
        return self.entity(t["entity_id"])

    def apply_template(self, eid: int, template_id: int, user: int = 1) -> dict:
        """The entity's tasks become the template's, in its order. Tasks it does not list are removed (disabled
        when they have versions); custom tasks are kept, after the template's."""
        e = self.one("SELECT * FROM entities WHERE id = ?", (eid,), "shot or asset")
        tpl = self._template_of_kind(e["project_id"], template_id, e["kind"])
        with self.tx() as db:
            current = {r["name"]: dict(r) for r in db.execute("SELECT * FROM tasks WHERE entity_id = ?", (eid,))}
            for i, name in enumerate(tpl["tasks"]):
                if name in current:
                    db.execute("UPDATE tasks SET sort = ?, enabled = 1, custom = 0 WHERE id = ?", (i, current[name]["id"]))
                else:
                    db.execute("INSERT INTO tasks(entity_id, name, sort) VALUES (?,?,?)", (eid, name, i))
            extra = len(tpl["tasks"])
            for name, t in current.items():
                if name in tpl["tasks"]:
                    continue
                if t["custom"]:
                    db.execute("UPDATE tasks SET sort = ? WHERE id = ?", (extra, t["id"]))
                    extra += 1
                elif db.execute("SELECT 1 FROM versions WHERE task_id = ?", (t["id"],)).fetchone():
                    db.execute("UPDATE tasks SET enabled = 0, sort = ? WHERE id = ?", (extra, t["id"]))
                    extra += 1
                else:
                    db.execute("DELETE FROM tasks WHERE id = ?", (t["id"],))
            self._log(db, e["project_id"], user, "applied", f"template {tpl['name']} to {e['name']}", "entity", eid)
        self._changed(e["project_id"], "entities")
        return self.entity(eid)

    # ---------- uses (casting) ----------

    def add_use(self, parent_id: int, child_id: int, user: int = 1) -> dict:
        p = self.one("SELECT * FROM entities WHERE id = ?", (parent_id,), "shot or asset")
        c = self.one("SELECT * FROM entities WHERE id = ?", (child_id,), "asset")
        if c["kind"] != "asset" or c["project_id"] != p["project_id"] or parent_id == child_id:
            raise StoreError("Only another asset of the same project can be used")
        if self._reaches(child_id, parent_id):
            raise StoreError(f"{c['name']} already uses {p['name']}: that would be a loop")
        with self.tx() as db:
            db.execute("INSERT OR IGNORE INTO uses(parent_id, child_id) VALUES (?,?)", (parent_id, child_id))
            self._log(db, p["project_id"], user, "cast", f"{c['name']} in {p['name']}", "entity", parent_id)
        self._changed(p["project_id"], "entities")
        return self.entity(parent_id)

    def _reaches(self, start: int, goal: int) -> bool:
        seen, todo = set(), [start]
        while todo:
            n = todo.pop()
            if n == goal:
                return True
            if n not in seen:
                seen.add(n)
                todo += [r["child_id"] for r in self.q("SELECT child_id FROM uses WHERE parent_id = ?", (n,))]
        return False

    def remove_use(self, parent_id: int, child_id: int) -> dict:
        p = self.one("SELECT * FROM entities WHERE id = ?", (parent_id,), "shot or asset")
        with self.tx() as db:
            db.execute("DELETE FROM uses WHERE parent_id = ? AND child_id = ?", (parent_id, child_id))
        self._changed(p["project_id"], "entities")
        return self.entity(parent_id)

    # ---------- versions (published files) ----------

    def _entity_dir(self, e: dict, root: str) -> Path:
        return Path(root) / ("shots" if e["kind"] == "shot" else f"assets/{e['asset_type']}") / e["name"]

    def versions(self, eid: int) -> list[dict]:
        return self.q("SELECT v.*, t.name AS task FROM versions v JOIN tasks t ON t.id = v.task_id "
                      "WHERE v.entity_id = ? ORDER BY t.sort, v.variant, v.number DESC", (eid,))

    def version(self, vid: int) -> dict:
        v = self.one("SELECT v.*, t.name AS task, e.name AS entity, e.kind AS entity_kind, e.project_id "
                     "FROM versions v JOIN tasks t ON t.id = v.task_id JOIN entities e ON e.id = v.entity_id "
                     "WHERE v.id = ?", (vid,), "version")
        v["uses"] = self.q("SELECT v.id, v.number, v.variant, t.name AS task, e.name AS entity FROM version_uses u "
                           "JOIN versions v ON v.id = u.used_id JOIN tasks t ON t.id = v.task_id "
                           "JOIN entities e ON e.id = v.entity_id WHERE u.version_id = ?", (vid,))
        return v

    def version_path(self, vid: int) -> Path:
        v = self.version(vid)
        root = self.project(v["project_id"])["root"]
        return Path(root) / v["path"]

    def publish(self, task_id: int, variant: str = "base", *, user: int = 1, ext: str = ".blend",
                write: Callable[[Path], None], description: str = "", origin: str = "cairn",
                source_id: int | None = None, uses: list[int] | None = None) -> dict:
        """Creates the next version of a task and variant: `write(path)` makes the file (or folder when ext is "").
        The number is reserved in the database first, so two publishers never get the same one; nothing is overwritten."""
        check_name(variant, "variant")
        if ext and not re.fullmatch(r"\.[A-Za-z0-9]{1,8}", ext):
            raise StoreError(f"Bad file extension {ext}")
        t = self.one("SELECT t.*, e.project_id FROM tasks t JOIN entities e ON e.id = t.entity_id WHERE t.id = ?",
                     (task_id,), "task")
        if not t["enabled"]:
            raise StoreError(f"Task {t['name']} is disabled")
        e = self.one("SELECT * FROM entities WHERE id = ?", (t["entity_id"],))
        root = self.project(e["project_id"])["root"]
        folder = self._entity_dir(e, root) / t["name"] / variant
        stem = f"{e['name']}_{t['name']}_{variant}"
        with self.tx() as db:
            n = db.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM versions WHERE task_id = ? AND variant = ?",
                           (task_id, variant)).fetchone()[0]
            while any(folder.glob(f"{stem}_v{n:03d}*")):  # a file made by hand took the number: never overwrite it
                n += 1
            path = folder / f"{stem}_v{n:03d}{ext}"
            rel = path.relative_to(root).as_posix()
            vid = db.execute(
                "INSERT INTO versions(entity_id, task_id, variant, number, kind, path, description, origin, source_id, "
                "created_at, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (e["id"], task_id, variant, n, ext.lstrip(".").lower() or "folder", rel, description, origin, source_id,
                 now(), user)).lastrowid
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            write(path)
            if not path.exists():
                raise StoreError(f"{path.name} was not created")
        except BaseException:
            with self.tx() as db:
                db.execute("DELETE FROM versions WHERE id = ?", (vid,))
            raise
        with self.tx() as db:
            for u in uses or []:
                db.execute("INSERT OR IGNORE INTO version_uses(version_id, used_id) VALUES (?,?)", (vid, u))
            if t["status"] == "ns":
                db.execute("UPDATE tasks SET status = 'wip' WHERE id = ?", (task_id,))
            db.execute("UPDATE entities SET updated_at = ?, updated_by = ? WHERE id = ?", (now(), user, e["id"]))
            self._log(db, e["project_id"], user, "published", f"{e['name']} {t['name']} {variant} v{n:03d}", "version", vid)
        self._changed(e["project_id"], "versions")
        return self.version(vid)

    def copy_version(self, task_id: int, variant: str, source_id: int, user: int = 1, description: str = "") -> dict:
        src = self.version_path(source_id)
        if not src.exists():
            raise StoreError(f"{src.name} is missing on disk")
        ext = "" if src.is_dir() else src.suffix
        return self.publish(task_id, variant, user=user, ext=ext, source_id=source_id,
                            description=description or f"copy of {src.name}",
                            write=lambda p: shutil.copytree(src, p) if src.is_dir() else shutil.copy2(src, p))

    def update_version(self, vid: int, description: str | None = None, uses: list[int] | None = None) -> dict:
        v = self.version(vid)
        with self.tx() as db:
            if description is not None:
                db.execute("UPDATE versions SET description = ? WHERE id = ?", (description, vid))
            if uses is not None:
                db.execute("DELETE FROM version_uses WHERE version_id = ?", (vid,))
                for u in uses:
                    db.execute("INSERT OR IGNORE INTO version_uses(version_id, used_id) VALUES (?,?)", (vid, u))
        self._changed(v["project_id"], "versions")
        return self.version(vid)

    def project_versions(self, pid: int, limit: int = 500) -> list[dict]:
        """For pickers (notes, review): newest first."""
        return self.q("SELECT v.id, v.number, v.variant, v.kind, v.created_at, t.name AS task, e.name AS entity, "
                      "e.kind AS entity_kind, e.id AS entity_id FROM versions v JOIN tasks t ON t.id = v.task_id "
                      "JOIN entities e ON e.id = v.entity_id WHERE e.project_id = ? ORDER BY v.id DESC LIMIT ?", (pid, limit))

    # ---------- thumbnails ----------

    def set_thumbnail(self, eid: int, data: bytes, ext: str) -> dict:
        ext = ext.lower()
        if ext not in THUMB_EXTS:
            raise StoreError("Thumbnails are PNG, JPG or WebP images")
        e = self.one("SELECT * FROM entities WHERE id = ?", (eid,), "shot or asset")
        root = Path(self.project(e["project_id"])["root"])
        folder = root / ".cairn" / "thumbs"
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{e['kind']}_{eid}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}"  # a new name: no stale browser cache
        (folder / name).write_bytes(data)
        with self.tx() as db:
            db.execute("UPDATE entities SET thumbnail = ? WHERE id = ?", (f".cairn/thumbs/{name}", eid))
        self._changed(e["project_id"], "entities")
        return self.entity(eid)

    def thumbnail_path(self, eid: int) -> Path:
        e = self.one("SELECT * FROM entities WHERE id = ?", (eid,), "shot or asset")
        if not e["thumbnail"]:
            raise NotFound("No thumbnail")
        return Path(self.project(e["project_id"])["root"]) / e["thumbnail"]

    # ---------- notes ----------

    def notes(self, pid: int, status: str | None = None, target: str | None = None, target_id: int | None = None) -> list[dict]:
        sql = ("SELECT n.*, (SELECT COUNT(*) FROM replies r WHERE r.note_id = n.id) AS reply_count FROM notes n "
               "WHERE n.project_id = ?")
        args: list = [pid]
        if status:
            sql += " AND n.status = ?"
            args.append(status)
        if target:
            sql += " AND EXISTS (SELECT 1 FROM note_links l WHERE l.note_id = n.id AND l.target = ? AND l.target_id = ?)"
            args += [target, target_id]
        out = self.q(sql + " ORDER BY COALESCE(n.updated_at, n.created_at) DESC", args)
        for n in out:
            n["links"] = self._note_links(n["id"])
            n["assignees"] = [r["user_id"] for r in self.q("SELECT user_id FROM note_assignees WHERE note_id = ?", (n["id"],))]
        return out

    def _note_links(self, nid: int) -> list[dict]:
        out = []
        for l in self.q("SELECT * FROM note_links WHERE note_id = ? ORDER BY target, target_id", (nid,)):
            try:
                if l["target"] == "entity":
                    e = self.one("SELECT id, kind, name FROM entities WHERE id = ?", (l["target_id"],))
                    out.append({"target": "entity", "id": e["id"], "label": e["name"], "kind": e["kind"], "entity_id": e["id"]})
                elif l["target"] == "version":
                    v = self.version(l["target_id"])
                    out.append({"target": "version", "id": v["id"], "entity_id": v["entity_id"],
                                "label": f"{v['entity']} · {v['task']} · {v['variant']} · v{v['number']:03d}"})
                else:
                    t = self.one("SELECT t.id, t.name, e.name AS entity, e.id AS entity_id FROM tasks t "
                                 "JOIN entities e ON e.id = t.entity_id WHERE t.id = ?", (l["target_id"],))
                    out.append({"target": "task", "id": t["id"], "entity_id": t["entity_id"], "label": f"{t['entity']} · {t['name']}"})
            except NotFound:
                pass  # the linked item was deleted
        return out

    def note(self, nid: int) -> dict:
        n = self.one("SELECT * FROM notes WHERE id = ?", (nid,), "note")
        n["links"] = self._note_links(nid)
        n["assignees"] = [r["user_id"] for r in self.q("SELECT user_id FROM note_assignees WHERE note_id = ?", (nid,))]
        n["replies"] = self.q("SELECT * FROM replies WHERE note_id = ? ORDER BY id", (nid,))
        atts = self.q("SELECT * FROM attachments WHERE note_id = ? ORDER BY id", (nid,))
        n["attachments"] = [a for a in atts if a["reply_id"] is None]
        for r in n["replies"]:
            r["attachments"] = [a for a in atts if a["reply_id"] == r["id"]]
        return n

    def _check_links(self, db, pid: int, links: list[dict]) -> None:
        tables = {"entity": "SELECT project_id FROM entities WHERE id = ?",
                  "version": "SELECT e.project_id FROM versions v JOIN entities e ON e.id = v.entity_id WHERE v.id = ?",
                  "task": "SELECT e.project_id FROM tasks t JOIN entities e ON e.id = t.entity_id WHERE t.id = ?"}
        for l in links:
            if l.get("target") not in tables:
                raise StoreError(f"A note links shots, assets, versions or tasks, not {l.get('target')}")
            r = db.execute(tables[l["target"]], (l["id"],)).fetchone()
            if not r or r[0] != pid:
                raise StoreError(f"No {l['target']} {l['id']} in this project")

    def create_note(self, pid: int, title: str, content: str = "", links: list[dict] | None = None,
                    assignees: list[int] | None = None, frame: int | None = None, user: int = 1) -> dict:
        if not title.strip():
            raise StoreError("A note needs a title")
        links = links or []
        with self.tx() as db:
            self._check_links(db, pid, links)
            nid = db.execute("INSERT INTO notes(project_id, title, content, frame, created_at, created_by, updated_at) "
                             "VALUES (?,?,?,?,?,?,?)", (pid, title.strip(), content, frame, now(), user, now())).lastrowid
            for l in links:
                db.execute("INSERT OR IGNORE INTO note_links(note_id, target, target_id) VALUES (?,?,?)", (nid, l["target"], l["id"]))
            for u in assignees or []:
                db.execute("INSERT OR IGNORE INTO note_assignees(note_id, user_id) VALUES (?,?)", (nid, u))
            self._log(db, pid, user, "noted", title.strip(), "note", nid)
        self._changed(pid, "notes")
        return self.note(nid)

    def update_note(self, nid: int, title: str | None = None, content: str | None = None, status: str | None = None,
                    links: list[dict] | None = None, assignees: list[int] | None = None, user: int = 1) -> dict:
        n = self.one("SELECT * FROM notes WHERE id = ?", (nid,), "note")
        if status is not None and status not in ("open", "closed"):
            raise StoreError("A note is open or closed")
        with self.tx() as db:
            if links is not None:
                self._check_links(db, n["project_id"], links)
                db.execute("DELETE FROM note_links WHERE note_id = ?", (nid,))
                for l in links:
                    db.execute("INSERT OR IGNORE INTO note_links(note_id, target, target_id) VALUES (?,?,?)", (nid, l["target"], l["id"]))
            if assignees is not None:
                db.execute("DELETE FROM note_assignees WHERE note_id = ?", (nid,))
                for u in assignees:
                    db.execute("INSERT OR IGNORE INTO note_assignees(note_id, user_id) VALUES (?,?)", (nid, u))
            db.execute("UPDATE notes SET title = ?, content = ?, status = ?, updated_at = ? WHERE id = ?",
                       ((title or n["title"]).strip(), n["content"] if content is None else content,
                        status or n["status"], now(), nid))
            if status and status != n["status"]:
                self._log(db, n["project_id"], user, "closed" if status == "closed" else "reopened", n["title"], "note", nid)
        self._changed(n["project_id"], "notes")
        return self.note(nid)

    def reply(self, nid: int, content: str, user: int = 1) -> dict:
        n = self.one("SELECT * FROM notes WHERE id = ?", (nid,), "note")
        if not content.strip():
            raise StoreError("Empty reply")
        with self.tx() as db:
            db.execute("INSERT INTO replies(note_id, content, created_at, created_by) VALUES (?,?,?,?)", (nid, content, now(), user))
            db.execute("UPDATE notes SET updated_at = ? WHERE id = ?", (now(), nid))
            self._log(db, n["project_id"], user, "replied", f"on {n['title']}", "note", nid)
        self._changed(n["project_id"], "notes")
        return self.note(nid)

    def attach(self, nid: int, kind: str, value: str, name: str = "", reply_id: int | None = None,
               data: bytes | None = None, user: int = 1) -> dict:
        """kind 'url' (value = the URL) or 'file' (data saved in the project's .cairn/attachments, value = its path)."""
        n = self.one("SELECT * FROM notes WHERE id = ?", (nid,), "note")
        if kind == "url":
            if not re.match(r"^https?://", value):
                raise StoreError("Links must start with http:// or https://")
        elif kind == "file":
            if data is None:
                raise StoreError("No file data")
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name or "file").name)[:80] or "file"
            folder = Path(self.project(n["project_id"])["root"]) / ".cairn" / "attachments" / str(nid)
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe}"
            path.write_bytes(data)
            value, name = path.relative_to(self.project(n["project_id"])["root"]).as_posix(), name or safe
        else:
            raise StoreError("Attachments are urls or files")
        with self.tx() as db:
            db.execute("INSERT INTO attachments(note_id, reply_id, kind, value, name, created_at, created_by) VALUES (?,?,?,?,?,?,?)",
                       (nid, reply_id, kind, value, name or value, now(), user))
        self._changed(n["project_id"], "notes")
        return self.note(nid)

    def attachment_path(self, aid: int) -> Path:
        a = self.one("SELECT a.*, n.project_id FROM attachments a JOIN notes n ON n.id = a.note_id WHERE a.id = ?", (aid,), "attachment")
        if a["kind"] != "file":
            raise NotFound("Not a file attachment")
        return Path(self.project(a["project_id"])["root"]) / a["value"]

    # ---------- home, search ----------

    def activity(self, pid: int, limit: int = 40) -> list[dict]:
        return self.q("SELECT a.*, u.name AS user FROM activity a LEFT JOIN users u ON u.id = a.user_id "
                      "WHERE project_id = ? ORDER BY a.id DESC LIMIT ?", (pid, limit))

    def my_tasks(self, pid: int, user: int = 1) -> list[dict]:
        """Open tasks: assigned to the user, or unassigned in a single-user project; review and retake first."""
        return self.q(
            "SELECT t.id, t.name, t.status, e.id AS entity_id, e.name AS entity, e.kind, "
            "(SELECT MAX(number) FROM versions v WHERE v.task_id = t.id) AS latest FROM tasks t "
            "JOIN entities e ON e.id = t.entity_id WHERE e.project_id = ? AND t.enabled = 1 "
            "AND t.status IN ('wip','rev','ret') AND (t.assignee_id = ? OR t.assignee_id IS NULL) "
            "ORDER BY CASE t.status WHEN 'ret' THEN 0 WHEN 'rev' THEN 1 ELSE 2 END, e.name LIMIT 50", (pid, user))

    def search(self, pid: int, text: str, limit: int = 20) -> list[dict]:
        like = f"%{text.strip()}%"
        if not text.strip():
            return []
        out = [{"type": e["kind"], "id": e["id"], "label": e["name"], "detail": e["title"] or e["asset_type"] or e["sequence"] or ""}
               for e in self.q("SELECT e.*, s.name AS sequence FROM entities e LEFT JOIN sequences s ON s.id = e.sequence_id "
                               "WHERE e.project_id = ? AND (e.name LIKE ? OR e.title LIKE ? OR e.description LIKE ?) "
                               "ORDER BY e.name LIMIT ?", (pid, like, like, like, limit))]
        out += [{"type": "note", "id": n["id"], "label": n["title"], "detail": n["status"]}
                for n in self.q("SELECT * FROM notes WHERE project_id = ? AND (title LIKE ? OR content LIKE ?) "
                                "ORDER BY id DESC LIMIT ?", (pid, like, like, limit))]
        out += [{"type": "version", "id": v["id"], "entity_id": v["entity_id"],
                 "label": f"{v['entity']} · {v['task']} · {v['variant']} · v{v['number']:03d}", "detail": v["kind"]}
                for v in self.q("SELECT v.*, t.name AS task, e.name AS entity FROM versions v JOIN tasks t ON t.id = v.task_id "
                                "JOIN entities e ON e.id = v.entity_id WHERE e.project_id = ? AND "
                                "(e.name || '_' || t.name || '_' || v.variant || '_v' || printf('%03d', v.number)) LIKE ? "
                                "ORDER BY v.id DESC LIMIT ?", (pid, like.replace(" ", "_"), limit))]
        return out[:limit]
