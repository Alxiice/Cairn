"""HTTP API over the store (REST + JSON), live change events (Server-Sent Events), plugin routes, and the web UI.

The UI only talks to this API, so the same server can run inside the desktop app (127.0.0.1) or on another
machine for a team (`python -m cairn serve --host 0.0.0.0`). There is no authentication yet: share it only on
a trusted network.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .blender import BlenderError, create_empty, find_blender
from .plugins import PluginContext, discover, load
from .store import NotFound, Store, StoreError

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
MAX_UPLOAD = 4 * 1024 ** 3  # 4 GB per published file


# ---------- request bodies (validated at the boundary) ----------

class ProjectIn(BaseModel):
    name: str
    code: str
    root: str = ""
    description: str = ""
    fps: int = Field(24, ge=1, le=240)
    width: int = Field(1920, ge=16, le=16384)
    height: int = Field(1080, ge=16, le=16384)


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    fps: int | None = Field(None, ge=1, le=240)
    width: int | None = Field(None, ge=16, le=16384)
    height: int | None = Field(None, ge=16, le=16384)
    asset_types: list[str] | None = None
    default_shot_template: int | None = None
    default_asset_template: int | None = None


class SequenceIn(BaseModel):
    name: str
    description: str = ""
    sort: int | None = None


class TemplateIn(BaseModel):
    name: str
    kind: Literal["shot", "asset"]
    tasks: list[str]


class EntityIn(BaseModel):
    kind: Literal["shot", "asset"]
    name: str
    template_id: int | None = None
    title: str = ""
    description: str = ""
    sequence_id: int | None = None
    asset_type: str = ""
    head: int | None = None
    tail: int | None = None


class EntityPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    sequence_id: int | None = None
    asset_type: str | None = None
    head: int | None = None
    tail: int | None = None
    cut_in: int | None = None
    cut_out: int | None = None


class TaskIn(BaseModel):
    name: str


class TaskPatch(BaseModel):
    status: str | None = None
    assignee_id: int | None = None
    sort: int | None = None
    enabled: bool | None = None


class TemplateApply(BaseModel):
    template_id: int


class UseIn(BaseModel):
    child_id: int


class PublishIn(BaseModel):
    task_id: int
    variant: str = "base"
    mode: Literal["empty", "copy"]
    source_id: int | None = None
    description: str = ""
    uses: list[int] = []


class VersionPatch(BaseModel):
    description: str | None = None
    uses: list[int] | None = None


class Link(BaseModel):
    target: Literal["entity", "version", "task"]
    id: int


class NoteIn(BaseModel):
    title: str
    content: str = ""
    links: list[Link] = []
    assignees: list[int] = []
    frame: int | None = None


class NotePatch(BaseModel):
    title: str | None = None
    content: str | None = None
    status: Literal["open", "closed"] | None = None
    links: list[Link] | None = None
    assignees: list[int] | None = None


class ReplyIn(BaseModel):
    content: str


class FolderIn(BaseModel):
    path: str


class UrlAttachment(BaseModel):
    url: str
    name: str = ""
    reply_id: int | None = None


# ---------- live events ----------

class Events:
    """Fan-out of change notices to every connected client (SSE). store.on_change runs on worker threads."""

    def __init__(self):
        self.queues: set[asyncio.Queue] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def publish(self, project_id, what: str):
        if self.loop is None:
            return
        msg = json.dumps({"project": project_id, "what": what})
        for q in list(self.queues):
            self.loop.call_soon_threadsafe(q.put_nowait, msg)

    async def stream(self, request: Request):
        q: asyncio.Queue = asyncio.Queue()
        self.queues.add(q)
        try:
            yield "event: hello\ndata: {}\n\n"
            while not await request.is_disconnected():
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"event: change\ndata: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            self.queues.discard(q)


def create_app(data_dir: Path | str, plugin_folders: list[str] | None = None, blender: str = "",
               web_dist: Path | None = WEB_DIST) -> FastAPI:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    events = Events()
    if (data_dir / "b3dprod.db").exists() and not (data_dir / "cairn.db").exists():  # Cairn was named B3DProd
        for suffix in ("-wal", "-shm", ""):  # the main file last, so a failed move is retried at the next start
            if (data_dir / f"b3dprod.db{suffix}").exists():
                (data_dir / f"b3dprod.db{suffix}").rename(data_dir / f"cairn.db{suffix}")
    store = Store(data_dir / "cairn.db", on_change=events.publish)
    @asynccontextmanager
    async def lifespan(_app):
        events.loop = asyncio.get_running_loop()  # change notices from worker threads are queued on this loop
        yield
        with store.lock:
            store.db.close()  # the database file is free once the server stops (restart, tests)

    app = FastAPI(title="Cairn", version=__version__, lifespan=lifespan)
    app.state.store = store

    @app.middleware("http")
    async def no_stale_pages(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache"  # pages pick up a new build; /assets/* names are hashed
        return response

    @app.exception_handler(NotFound)
    async def _nf(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(StoreError)
    async def _se(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(BlenderError)
    async def _be(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    def blender_exe() -> Path:
        exe = find_blender(blender)
        if not exe:
            raise BlenderError("Blender not found on the server: start it with --blender <path>")
        return exe

    r = APIRouter(prefix="/api")

    @r.get("/health")
    def health():
        exe = find_blender(blender)
        return {"app": "cairn", "version": __version__, "blender": str(exe) if exe else ""}

    @r.post("/server/{action}")
    def control_server(action: Literal["stop", "restart"], request: Request):
        """Stops or restarts a tray server (python -m cairn stop / restart). Only from the server's own machine."""
        if request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(403, "Only the server's own machine can stop or restart it")
        do = getattr(app.state, f"{action}_server", None)
        if do is None:
            raise StoreError("This server was not started from the system tray: stop it where it runs")
        do()
        return {}

    @r.get("/events")
    async def stream(request: Request):
        return StreamingResponse(events.stream(request), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @r.get("/users")
    def users():
        return store.users()

    # projects
    @r.get("/projects")
    def projects():
        return store.projects()

    @r.post("/projects")
    def create_project(b: ProjectIn):
        root = b.root.strip() or str(data_dir / "projects" / b.code)
        return store.create_project(b.name, b.code, root, fps=b.fps, width=b.width, height=b.height, description=b.description)

    @r.get("/projects/{pid}")
    def project(pid: int):
        return store.project(pid)

    @r.patch("/projects/{pid}")
    def patch_project(pid: int, b: ProjectPatch):
        return store.update_project(pid, **b.model_dump(exclude_unset=True))

    @r.get("/projects/{pid}/sequences")
    def sequences(pid: int):
        return store.sequences(pid)

    @r.post("/projects/{pid}/sequences")
    def create_sequence(pid: int, b: SequenceIn):
        return store.create_sequence(pid, b.name, b.description)

    @r.patch("/sequences/{sid}")
    def patch_sequence(sid: int, b: SequenceIn):
        return store.update_sequence(sid, b.name, b.description, b.sort)

    @r.delete("/sequences/{sid}")
    def delete_sequence(sid: int):
        store.delete_sequence(sid)
        return {}

    @r.get("/projects/{pid}/templates")
    def templates(pid: int):
        return store.templates(pid)

    @r.post("/projects/{pid}/templates")
    def create_template(pid: int, b: TemplateIn):
        return store.save_template(pid, b.name, b.kind, b.tasks)

    @r.put("/projects/{pid}/templates/{tid}")
    def save_template(pid: int, tid: int, b: TemplateIn):
        return store.save_template(pid, b.name, b.kind, b.tasks, tid=tid)

    @r.delete("/templates/{tid}")
    def delete_template(tid: int):
        store.delete_template(tid)
        return {}

    # entities
    @r.get("/projects/{pid}/entities")
    def entities(pid: int, kind: Literal["shot", "asset"] | None = None):
        return store.entities(pid, kind)

    @r.post("/projects/{pid}/entities")
    def create_entity(pid: int, b: EntityIn):
        return store.create_entity(pid, **b.model_dump())

    @r.get("/entities/{eid}")
    def entity(eid: int):
        return store.entity(eid)

    @r.patch("/entities/{eid}")
    def patch_entity(eid: int, b: EntityPatch):
        return store.update_entity(eid, **b.model_dump(exclude_unset=True))

    @r.delete("/entities/{eid}")
    def delete_entity(eid: int):
        store.delete_entity(eid)
        return {}

    @r.post("/entities/{eid}/apply-template")
    def apply_template(eid: int, b: TemplateApply):
        return store.apply_template(eid, b.template_id)

    @r.post("/entities/{eid}/tasks")
    def add_task(eid: int, b: TaskIn):
        return store.add_task(eid, b.name)

    @r.patch("/tasks/{task_id}")
    def patch_task(task_id: int, b: TaskPatch):
        return store.update_task(task_id, **b.model_dump(exclude_unset=True))

    @r.delete("/tasks/{task_id}")
    def remove_task(task_id: int):
        return store.remove_task(task_id)

    @r.post("/entities/{eid}/uses")
    def add_use(eid: int, b: UseIn):
        return store.add_use(eid, b.child_id)

    @r.delete("/entities/{eid}/uses/{child_id}")
    def remove_use(eid: int, child_id: int):
        return store.remove_use(eid, child_id)

    @r.post("/entities/{eid}/thumbnail")
    async def thumbnail(eid: int, file: UploadFile = File(...)):
        data = await file.read()
        if len(data) > 20 * 1024 ** 2:
            raise StoreError("Thumbnails are limited to 20 MB")
        return store.set_thumbnail(eid, data, Path(file.filename or "").suffix)

    @r.get("/entities/{eid}/thumbnail")
    def get_thumbnail(eid: int):
        return FileResponse(store.thumbnail_path(eid), headers={"Cache-Control": "max-age=31536000, immutable"})

    # versions
    @r.get("/entities/{eid}/versions")
    def versions(eid: int):
        return store.versions(eid)

    @r.get("/projects/{pid}/versions")
    def project_versions(pid: int):
        return store.project_versions(pid)

    @r.post("/entities/{eid}/versions")
    def publish(eid: int, b: PublishIn):
        task = store.one("SELECT entity_id FROM tasks WHERE id = ?", (b.task_id,), "task")
        if task["entity_id"] != eid:
            raise StoreError("This task belongs to another shot or asset")
        if b.mode == "copy":
            if not b.source_id:
                raise StoreError("Pick the version to copy")
            v = store.copy_version(b.task_id, b.variant, b.source_id, description=b.description)
        else:
            exe = blender_exe()
            v = store.publish(b.task_id, b.variant, write=lambda p: create_empty(exe, p), description=b.description)
        return store.update_version(v["id"], uses=b.uses) if b.uses else v

    @r.post("/entities/{eid}/versions/upload")
    async def publish_upload(eid: int, task_id: int = Form(...), variant: str = Form("base"),
                             description: str = Form(""), file: UploadFile = File(...)):
        task = store.one("SELECT entity_id FROM tasks WHERE id = ?", (task_id,), "task")
        if task["entity_id"] != eid:
            raise StoreError("This task belongs to another shot or asset")
        ext = Path(file.filename or "").suffix

        def write(path: Path):
            size = 0
            with open(path, "wb") as out:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise StoreError("File too big")
                    out.write(chunk)
        return await asyncio.to_thread(store.publish, task_id, variant, write=write, ext=ext,
                                       description=description or f"uploaded {Path(file.filename or '').name}")

    @r.get("/versions/{vid}")
    def version(vid: int):
        v = store.version(vid)
        v["abs_path"] = str(store.version_path(vid))  # for the desktop app's "Open in Blender" on the same machine
        return v

    @r.patch("/versions/{vid}")
    def patch_version(vid: int, b: VersionPatch):
        return store.update_version(vid, **b.model_dump(exclude_unset=True))

    @r.get("/versions/{vid}/file")
    def version_file(vid: int, name: str = ""):
        """The file of a version (videos stream with range requests); for a folder, `name` picks a file inside."""
        path = store.version_path(vid)
        if path.is_dir():
            files = sorted(p.name for p in path.iterdir() if p.is_file())
            if not name:
                return {"files": files}
            if name not in files:
                raise NotFound("No such file in this version")
            path = path / name
        if not path.is_file():
            raise NotFound("The file is missing on disk")
        return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")

    # notes
    @r.get("/projects/{pid}/notes")
    def notes(pid: int, status: Literal["open", "closed"] | None = None,
              target: Literal["entity", "version", "task"] | None = None, target_id: int | None = None):
        return store.notes(pid, status, target, target_id)

    @r.post("/projects/{pid}/notes")
    def create_note(pid: int, b: NoteIn):
        return store.create_note(pid, b.title, b.content, [l.model_dump() for l in b.links], b.assignees, b.frame)

    @r.get("/notes/{nid}")
    def note(nid: int):
        return store.note(nid)

    @r.patch("/notes/{nid}")
    def patch_note(nid: int, b: NotePatch):
        d = b.model_dump(exclude_unset=True)
        if "links" in d and d["links"] is not None:
            d["links"] = [dict(l) for l in d["links"]]
        return store.update_note(nid, **d)

    @r.post("/notes/{nid}/replies")
    def reply(nid: int, b: ReplyIn):
        return store.reply(nid, b.content)

    @r.post("/notes/{nid}/links")
    def add_url(nid: int, b: UrlAttachment):
        return store.attach(nid, "url", b.url, b.name, b.reply_id)

    @r.post("/notes/{nid}/attachments")
    async def attach_file(nid: int, file: UploadFile = File(...), reply_id: int | None = Form(None)):
        data = await file.read()
        if len(data) > 200 * 1024 ** 2:
            raise StoreError("Attachments are limited to 200 MB")
        return store.attach(nid, "file", "", file.filename or "file", reply_id, data)

    @r.get("/attachments/{aid}")
    def attachment(aid: int):
        return FileResponse(store.attachment_path(aid))

    # home, search
    @r.get("/projects/{pid}/activity")
    def activity(pid: int):
        return store.activity(pid)

    @r.get("/projects/{pid}/my-tasks")
    def my_tasks(pid: int):
        return store.my_tasks(pid)

    @r.get("/projects/{pid}/search")
    def search(pid: int, q: str = ""):
        return store.search(pid, q)

    # plugins: folders given at start (CLI, ~/.cairn/settings.json) plus folders added in Settings (<data>/server.json)
    config_path = data_dir / "server.json"

    def read_config() -> dict:
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    startup_folders = [str(Path(f).resolve()) for f in (plugin_folders or [])]
    added_folders = [f for f in read_config().get("pluginFolders", []) if f not in startup_folders]
    plugins: list = []
    ctx = PluginContext(store=store, data_dir=data_dir, helpers={"blender": blender_exe, "events": events})

    def install(folders: list[str]) -> list:
        """Loads the plugins found in these folders that are not loaded yet, and serves their routes and pages."""
        new = [p for p in discover(folders) if p.id not in {q.id for q in plugins}]
        for p in new:
            load(p, ctx)
            if p.router is not None:
                app.include_router(p.router, prefix=f"/api/plugins/{p.id}")
            if p.ui is not None:
                app.mount(f"/plugins/{p.id}", StaticFiles(directory=p.ui, html=True), name=f"plugin-{p.id}")
            plugins.append(p)
        routes = app.router.routes  # the web UI mounted at "/" must stay last, or it would hide the new routes
        for route in [x for x in routes if getattr(x, "name", "") == "web"]:
            routes.remove(route)
            routes.append(route)
        app.openapi_schema = None  # /docs lists the new routes
        return new

    def local_only(request: Request):
        if request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(403, "Only the server's own machine can change its plugins")

    def folder_list() -> list[dict]:
        out = []
        for f, source in [(f, "startup") for f in startup_folders] + [(f, "added") for f in added_folders]:
            found = [p.id for p in discover([f])]
            out.append({"path": f, "source": source, "exists": Path(f).is_dir(), "plugins": found,
                        "loaded": [i for i in found if i in {p.id for p in plugins}]})
        return out

    @r.get("/plugins")
    def list_plugins():
        return [p.public() for p in plugins]

    @r.get("/plugin-folders")
    def plugin_folders_list():
        return folder_list()

    @r.post("/plugin-folders")
    def add_plugin_folder(b: FolderIn, request: Request):
        local_only(request)
        folder = Path(b.path.strip().strip('"')).expanduser()
        if not folder.is_dir():
            raise StoreError(f"{folder} is not a folder on the server's machine")
        if not discover([folder]):
            raise StoreError(f"No plugin in {folder}: a plugin folder holds a plugin.json, or holds plugin folders")
        path = str(folder.resolve())
        if path not in startup_folders + added_folders:
            added_folders.append(path)
            config = read_config()
            config["pluginFolders"] = added_folders
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        new = install([path])
        events.publish(None, "plugins")
        return {"folders": folder_list(), "loaded": [p.public() for p in new]}

    @r.delete("/plugin-folders")
    def remove_plugin_folder(path: str, request: Request):
        local_only(request)
        if path in startup_folders:
            raise StoreError("This folder comes from the start command or ~/.cairn/settings.json: remove it there")
        if path not in added_folders:
            raise NotFound("No such plugin folder")
        added_folders.remove(path)
        config = read_config()
        config["pluginFolders"] = added_folders
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        events.publish(None, "plugins")
        return {"folders": folder_list(), "restart": True}  # loaded code cannot be unloaded: gone after a restart

    app.include_router(r)
    if web_dist and web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    install(startup_folders + added_folders)
    return app

