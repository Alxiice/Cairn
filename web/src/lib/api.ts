// The only way the UI talks to the data: the server's HTTP API (same origin, or the dev proxy).

export type Status = 'ns' | 'wip' | 'rev' | 'ret' | 'app' | 'skip'
export const STATUSES: { id: Status; label: string }[] = [
  { id: 'ns', label: 'Not started' }, { id: 'wip', label: 'WIP' }, { id: 'rev', label: 'Review' },
  { id: 'ret', label: 'Retake' }, { id: 'app', label: 'Approved' }, { id: 'skip', label: 'Skipped' },
]
export const statusLabel = (s: string) => STATUSES.find((x) => x.id === s)?.label ?? s

export interface Project {
  id: number; name: string; code: string; description: string; fps: number; width: number; height: number
  root: string; asset_types: string[]; default_shot_template: number | null; default_asset_template: number | null
}
export interface Sequence { id: number; name: string; description: string; sort: number; shot_count: number }
export interface Template { id: number; name: string; kind: 'shot' | 'asset'; tasks: string[] }
export interface TaskRow { id: number; name: string; status: Status; enabled: boolean; latest: number | null; assignee_id: number | null }
export interface Task extends TaskRow { sort: number; custom: boolean; version_count: number; entity_id: number }
export interface EntityRow {
  id: number; kind: 'shot' | 'asset'; name: string; title: string; description: string; sequence: string | null
  sequence_id: number | null; asset_type: string; head: number | null; tail: number | null; cut_in: number | null
  cut_out: number | null; thumbnail: string; updated_at: string; tasks: TaskRow[]; open_notes: number; used_in: number
  uses: number; version_count: number
}
export interface Ref { id: number; kind: 'shot' | 'asset'; name: string; asset_type: string }
export interface Entity extends Omit<EntityRow, 'tasks' | 'uses' | 'used_in'> {
  tasks: Task[]; uses: Ref[]; used_in: Ref[]; created_at: string
}
export interface Version {
  id: number; entity_id: number; task_id: number; task: string; variant: string; number: number; kind: string
  path: string; description: string; origin: string; source_id: number | null; created_at: string
  entity?: string; abs_path?: string
}
export interface VersionPick { id: number; number: number; variant: string; kind: string; task: string; entity: string; entity_kind: string; entity_id: number; created_at: string }
export interface LinkRef { target: 'entity' | 'version' | 'task'; id: number; label?: string; entity_id?: number; kind?: string }
export interface Attachment { id: number; kind: 'url' | 'file'; value: string; name: string }
export interface Reply { id: number; content: string; created_at: string; created_by: number; attachments: Attachment[] }
export interface Note {
  id: number; title: string; content: string; status: 'open' | 'closed'; frame: number | null; created_at: string
  updated_at: string; created_by: number; links: LinkRef[]; reply_count?: number; replies?: Reply[]
  attachments?: Attachment[]; assignees?: number[]
}
export interface Activity { id: number; at: string; verb: string; label: string; target: string; target_id: number; user: string }
export interface Hit { type: 'shot' | 'asset' | 'note' | 'version'; id: number; label: string; detail: string; entity_id?: number }
export interface PluginInfo { id: string; name: string; description: string; icon: string; ui: string; error: string }
export interface PluginFolder { path: string; source: 'startup' | 'added'; exists: boolean; plugins: string[]; loaded: string[] }

export class ApiError extends Error {}

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method }
  if (body instanceof FormData) init.body = body
  else if (body !== undefined) {
    init.body = JSON.stringify(body)
    init.headers = { 'Content-Type': 'application/json' }
  }
  const r = await fetch('/api' + url, init)
  if (!r.ok) {
    let detail = r.statusText
    try {
      const j = await r.json()
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* not JSON */ }
    throw new ApiError(detail)
  }
  return r.status === 204 ? (undefined as T) : r.json()
}

export const api = {
  get: <T>(url: string) => call<T>('GET', url),
  post: <T>(url: string, body?: unknown) => call<T>('POST', url, body ?? {}),
  put: <T>(url: string, body: unknown) => call<T>('PUT', url, body),
  patch: <T>(url: string, body: unknown) => call<T>('PATCH', url, body),
  del: <T>(url: string) => call<T>('DELETE', url),
}

export const thumbUrl = (e: { id: number; thumbnail: string }) =>
  e.thumbnail ? `/api/entities/${e.id}/thumbnail?v=${encodeURIComponent(e.thumbnail)}` : ''
export const vname = (v: { variant: string; number: number; task?: string }) =>
  `${v.task ? v.task + ' · ' : ''}${v.variant} · v${String(v.number).padStart(3, '0')}`
export const vnum = (n: number | null) => (n ? 'v' + String(n).padStart(3, '0') : '')

export function ago(iso: string): string {
  if (!iso) return '—'
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  if (s < 172800) return 'yesterday'
  return `${Math.floor(s / 86400)} days ago`
}

// The desktop window adds these (pywebview); in a browser they are missing.
interface Bridge { open_in_blender(path: string): Promise<string>; open_folder(path: string): Promise<string>; pick_folder(): Promise<string> }
export const desktop = (): Bridge | null => (window as unknown as { pywebview?: { api: Bridge } }).pywebview?.api ?? null
