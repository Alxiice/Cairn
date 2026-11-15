<script lang="ts">
  import { api, type Project } from '../lib/api'
  import { act, app, pickProject } from '../lib/state.svelte'

  // First run (no project yet) and "+ New project…".
  let name = $state('')
  let code = $state('')
  let root = $state('')
  let fps = $state(24)
  const auto = $derived(name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, ''))

  async function create(e: Event) {
    e.preventDefault()
    const p = await act(() => api.post<Project>('/projects', { name, code: code || auto, root, fps }), `Project ${name} created`)
    if (p) {
      app.projects = [...app.projects, p]
      pickProject(p)
    }
  }
</script>

<div class="wrap">
  <form class="panel card" onsubmit={create}>
    <img src="/logo.svg" alt="Cairn" width="56" height="56" />
    <h1>{app.projects.length ? 'New project' : 'Welcome to Cairn'}</h1>
    <p class="muted">A project holds sequences, shots, assets, their tasks and every published file.</p>
    <label class="stack">Name<input class="field" bind:value={name} placeholder="Outer Wilds AMV" required /></label>
    <label class="stack">Code<input class="field" bind:value={code} placeholder={auto || 'amv'} pattern="[a-z0-9]+(_[a-z0-9]+)*" /></label>
    <label class="stack">Folder on the server<input class="field" bind:value={root} placeholder="empty: next to the database" /></label>
    <label class="stack">Frame rate<input class="field" type="number" min="1" max="240" bind:value={fps} /></label>
    <button class="btn primary">Create the project</button>
  </form>
</div>

<style>
  .wrap { min-height: 100%; display: flex; align-items: center; justify-content: center; padding: 24px; }
  .card { width: 440px; padding: 28px; display: flex; flex-direction: column; gap: 12px; }
  h1 { font-size: 24px; }
  p { margin: 0; }
</style>
