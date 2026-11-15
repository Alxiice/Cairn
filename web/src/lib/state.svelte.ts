// App-wide state (Svelte 5 runes): the project, plugins, the live connection, routing and messages.
import { api, ApiError, type PluginInfo, type Project } from './api'

export const loadPlugins = async () => { app.plugins = await api.get<PluginInfo[]>('/plugins') }

export const app = $state({
  projects: [] as Project[],
  project: null as Project | null,
  plugins: [] as PluginInfo[],
  connected: false,
  /** Bumped on every change notice from the server: pages reload their data when it moves. */
  rev: 0,
  toast: null as { text: string; error: boolean } | null,
})

export const route = $state({ path: '', parts: [] as string[], query: {} as Record<string, string> })

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '')
  const [path, qs] = raw.split('?')
  route.path = path || 'home'
  route.parts = route.path.split('/')
  route.query = Object.fromEntries(new URLSearchParams(qs || ''))
}
window.addEventListener('hashchange', parseHash)
parseHash()

export const go = (path: string) => { location.hash = '#/' + path }

let toastTimer = 0
export function say(text: string, error = false) {
  app.toast = { text, error }
  clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => (app.toast = null), error ? 7000 : 3500)
}

/** Runs an API action and shows its error, if any. */
export async function act<T>(fn: () => Promise<T>, done = ''): Promise<T | undefined> {
  try {
    const r = await fn()
    if (done) say(done)
    return r
  } catch (e) {
    say(e instanceof ApiError ? e.message : String(e), true)
    return undefined
  }
}

/** Asks, then deletes a shot or asset. Its files stay on disk. */
export const deleteEntity = (e: { id: number; kind: string; name: string; version_count: number }) =>
  confirm(`Delete the ${e.kind} ${e.name}?` + (e.version_count ? ` Its ${e.version_count} versions leave the tracker; their files stay on disk.` : '')) &&
  act(() => api.del(`/entities/${e.id}`), `${e.name} deleted`)

const LAST = 'cairn.project'

export async function loadProjects() {
  app.projects = await api.get<Project[]>('/projects')
  let id = 0
  try { id = Number(localStorage.getItem(LAST)) } catch { /* storage blocked */ }
  app.project = app.projects.find((p) => p.id === id) ?? app.projects[0] ?? null
}

export function pickProject(p: Project) {
  app.project = p
  try { localStorage.setItem(LAST, String(p.id)) } catch { /* storage blocked */ }
  go('home')
}

export async function refreshProject() {
  if (!app.project) return
  const fresh = await api.get<Project>(`/projects/${app.project.id}`)
  app.project = fresh
  app.projects = app.projects.map((p) => (p.id === fresh.id ? fresh : p))
}

export function listen() {
  let bump = 0
  const es = new EventSource('/api/events')
  es.addEventListener('hello', () => (app.connected = true))
  es.addEventListener('change', (ev) => {
    const msg = JSON.parse((ev as MessageEvent).data) as { project: number | null; what: string }
    if (msg.project === null && msg.what === 'plugins') loadPlugins()
    else if (msg.project === null) loadProjects()
    if (msg.project !== null && msg.project !== app.project?.id) return
    if (msg.what === 'project') refreshProject()
    clearTimeout(bump)
    bump = window.setTimeout(() => app.rev++, 120) // one reload for a burst of changes
  })
  es.onerror = () => (app.connected = false) // EventSource reconnects by itself
}
