<script lang="ts">
  import { api, desktop, type PluginFolder, type Template } from '../lib/api'
  import { act, app, refreshProject, say } from '../lib/state.svelte'

  // Project settings: infos, task templates (and the defaults for new shots and assets), plugins, server.
  let templates = $state<Template[]>([])
  let health = $state<{ version: string; blender: string } | null>(null)
  let folders = $state<PluginFolder[]>([])
  let newFolder = $state('')
  let needRestart = $state(false)
  let theme = $state((window as unknown as { b3dTheme?: { get(): string } }).b3dTheme?.get() ?? 'dark')
  const setTheme = (t: string) => {
    theme = t
    ;(window as unknown as { b3dTheme?: { set(t: string): void } }).b3dTheme?.set(t)
  }
  const loadFolders = () => api.get<PluginFolder[]>('/plugin-folders').then((f) => (folders = f))
  $effect(() => { void app.plugins; loadFolders() })
  async function browse() {
    const picked = await desktop()?.pick_folder()
    if (picked) newFolder = picked
  }
  async function addFolder(e: Event) {
    e.preventDefault()
    const r = await act(() => api.post<{ loaded: { name: string }[] }>('/plugin-folders', { path: newFolder }))
    if (r) {
      say(r.loaded.length ? `Loaded ${r.loaded.map((p) => p.name).join(', ')}` : 'Folder added (its plugins were already loaded)')
      newFolder = ''
      loadFolders()
    }
  }
  async function removeFolder(f: PluginFolder) {
    if (!confirm(`Stop loading the plugins of ${f.path}? They go away when the server restarts.`)) return
    if (await act(() => api.del(`/plugin-folders?path=${encodeURIComponent(f.path)}`))) { needRestart = true; loadFolders() }
  }
  const restartServer = () => act(() => api.post('/server/restart'), 'The server restarts: this page reconnects in a few seconds')
  let info = $state({ name: '', description: '', fps: 24, width: 1920, height: 1080, types: '' })
  let edit = $state<{ id: number | null; name: string; kind: 'shot' | 'asset'; tasks: string[]; add: string } | null>(null)
  const p = $derived(app.project!)

  $effect(() => {
    void app.rev
    api.get<Template[]>(`/projects/${p.id}/templates`).then((t) => (templates = t))
  })
  $effect(() => { api.get<typeof health>('/health').then((h) => (health = h)) })
  $effect(() => {
    info = { name: p.name, description: p.description, fps: p.fps, width: p.width, height: p.height, types: p.asset_types.join(', ') }
  })

  async function saveInfo(e: Event) {
    e.preventDefault()
    await act(() => api.patch(`/projects/${p.id}`, { name: info.name, description: info.description, fps: info.fps, width: info.width, height: info.height,
      asset_types: info.types.split(',').map((t) => t.trim()).filter(Boolean) }), 'Project saved')
    refreshProject()
  }
  const setDefault = async (t: Template) => {
    await act(() => api.patch(`/projects/${p.id}`, { [t.kind === 'shot' ? 'default_shot_template' : 'default_asset_template']: t.id }), `${t.name} is the default for new ${t.kind}s`)
    refreshProject()
  }
  const isDefault = (t: Template) => t.id === (t.kind === 'shot' ? p.default_shot_template : p.default_asset_template)
  function addTaskToEdit(e: Event) {
    e.preventDefault()
    const name = edit!.add.trim()
    if (name && !edit!.tasks.includes(name)) edit!.tasks = [...edit!.tasks, name]
    edit!.add = ''
  }
  const moveTask = (i: number, d: number) => {
    const t = [...edit!.tasks]
    ;[t[i], t[i + d]] = [t[i + d], t[i]]
    edit!.tasks = t
  }
  async function saveTemplate() {
    const body = { name: edit!.name, kind: edit!.kind, tasks: edit!.tasks }
    const ok = await act(() => (edit!.id ? api.put(`/projects/${p.id}/templates/${edit!.id}`, body) : api.post(`/projects/${p.id}/templates`, body)), 'Template saved')
    if (ok) edit = null
  }
</script>

<div class="page">
  <h1>Settings</h1>
  <div class="grid">
    <form class="panel box" onsubmit={saveInfo}>
      <b>Project</b>
      <label class="stack">Name<input class="field" bind:value={info.name} required /></label>
      <label class="stack">Description<textarea class="field" rows="2" bind:value={info.description}></textarea></label>
      <div class="three">
        <label class="stack">FPS<input class="field" type="number" min="1" max="240" bind:value={info.fps} /></label>
        <label class="stack">Width<input class="field" type="number" bind:value={info.width} /></label>
        <label class="stack">Height<input class="field" type="number" bind:value={info.height} /></label>
      </div>
      <label class="stack">Asset types (comma separated)<input class="field" bind:value={info.types} /></label>
      <span class="muted small">Folder on the server: <span class="mono">{p.root}</span> · code <span class="mono">{p.code}</span></span>
      <button class="btn primary">Save</button>
    </form>


    <section class="panel box wide">
      <div class="line"><b class="grow">Task templates</b>
        <button class="btn" onclick={() => (edit = { id: null, name: '', kind: 'asset', tasks: [], add: '' })}>+ Template</button></div>
      <span class="muted small">A new shot or asset starts with its kind's default template (or the one picked when creating it). Its page can add custom tasks, remove tasks, or apply another template.</span>
      <table class="grid">
        <thead><tr><th>Template</th><th>For</th><th>Tasks</th><th>Default</th><th></th></tr></thead>
        <tbody>
          {#each templates as t (t.id)}
            <tr>
              <td><b>{t.name}</b></td><td>{t.kind}s</td>
              <td><div class="line">{#each t.tasks as n}<span class="tag">{n}</span>{/each}</div></td>
              <td><label class="check"><input type="radio" name={`default-${t.kind}`} checked={isDefault(t)} onchange={() => setDefault(t)} /> {isDefault(t) ? 'default' : ''}</label></td>
              <td class="nowrap">
                <button class="btn ghost small" onclick={() => (edit = { id: t.id, name: t.name, kind: t.kind, tasks: [...t.tasks], add: '' })}>Edit</button>
                <button class="btn ghost small danger" disabled={isDefault(t)} onclick={() => confirm(`Delete the ${t.name} template? Shots and assets keep their tasks.`) && act(() => api.del(`/templates/${t.id}`))}>Delete</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
      {#if edit}
        <div class="editor">
          <div class="line">
            <label class="stack grow">Name<input class="field" bind:value={edit.name} required /></label>
            <label class="stack">For<select class="field" bind:value={edit.kind} disabled={edit.id !== null}><option value="shot">shots</option><option value="asset">assets</option></select></label>
          </div>
          <div class="line">
            {#each edit.tasks as n, i (n)}
              <span class="tag">{#if i > 0}<button class="x" onclick={() => moveTask(i, -1)} aria-label={`Move ${n} earlier`}>‹</button>{/if}{n}{#if i < edit.tasks.length - 1}<button class="x" onclick={() => moveTask(i, 1)} aria-label={`Move ${n} later`}>›</button>{/if}<button class="x" onclick={() => (edit!.tasks = edit!.tasks.filter((x) => x !== n))} aria-label={`Remove ${n}`}>✕</button></span>
            {/each}
            <form onsubmit={addTaskToEdit}><input class="field" bind:value={edit.add} placeholder="+ task (enter)" pattern="[a-z0-9]+(_[a-z0-9]+)*" /></form>
          </div>
          <div class="line"><button class="btn primary" onclick={saveTemplate}>Save template</button><button class="btn ghost" onclick={() => (edit = null)}>Cancel</button>
            <span class="muted small">Editing a template does not change existing shots and assets: apply it again from their page.</span></div>
        </div>
      {/if}
    </section>

    <section class="panel box">
      <b>Appearance</b>
      <div class="seg" role="radiogroup" aria-label="Theme">
        {#each [['dark', 'Dark'], ['light', 'Light'], ['system', 'Like the system']] as [id, label]}
          <button role="radio" aria-checked={theme === id} class:on={theme === id} onclick={() => setTheme(id)}>{label}</button>
        {/each}
      </div>
      <span class="muted small">For this window and browser; plugin pages follow it.</span>
    </section>

    <section class="panel box wide">
      <b>Plugins</b>
      {#each app.plugins as pl}
        <div class="line"><span class="picon">{@html pl.icon}</span><b>{pl.name}</b><span class="muted small grow">{pl.description}</span>{#if pl.error}<span class="pill ret" title={pl.error}>error</span>{:else}<span class="pill app">on</span>{/if}</div>
        {#if pl.error}<span class="mono small" style:color="var(--bad)">{pl.error}</span>{/if}
      {:else}<span class="muted">No plugin loaded yet.</span>{/each}
      <span class="label">Plugin folders</span>
      {#each folders as f (f.path)}
        <div class="line">
          <span class="mono small grow">{f.path}</span>
          {#if !f.exists}<span class="pill ret">missing</span>{/if}
          <span class="muted small">{f.plugins.length ? f.plugins.join(', ') : 'no plugin'}</span>
          {#if f.source === 'added'}<button class="btn ghost small danger" onclick={() => removeFolder(f)}>Remove</button>
          {:else}<span class="tag" title="Given when the server started (--plugins or ~/.cairn/settings.json)">at start</span>{/if}
        </div>
      {:else}<span class="muted small">None.</span>{/each}
      <form class="line" onsubmit={addFolder}>
        <input class="field grow" bind:value={newFolder} placeholder="A folder on the server's machine, e.g. E:\Documents\TRAVAIL\OW\apps\CinematicOW" aria-label="Plugin folder" />
        {#if desktop()}<button type="button" class="btn" onclick={browse}>Browse…</button>{/if}
        <button class="btn primary" disabled={!newFolder.trim()}>Add the folder</button>
      </form>
      <span class="muted small">A plugin folder holds a <span class="mono">plugin.json</span>, or holds plugin folders. Its plugins load at once and appear in the left rail; the server remembers the folder. Only the server's own machine can add or remove folders.</span>
      {#if needRestart}
        <div class="line"><span class="small" style:color="var(--accent-text)">Removed plugins stay loaded until the server restarts.</span><button class="btn small" onclick={restartServer}>Restart the server</button></div>
      {/if}
    </section>

    <section class="panel box">
      <b>Server</b>
      <span class="muted small">Cairn {health?.version} · Blender on the server: <span class="mono">{health?.blender || 'not found'}</span></span>
      <span class="muted small">Address: <span class="mono">{location.origin}</span>. To share a project, run <span class="mono">py -m cairn serve --host 0.0.0.0</span> on one machine and open its address from the others (no login yet: trusted network only).</span>
    </section>
  </div>
</div>

<style>
  .page { padding: 16px 18px; display: flex; flex-direction: column; gap: 14px; }
  h1 { font-size: 22px; }
  .grid { display: flex; flex-wrap: wrap; gap: 14px; }
  .box { flex: 1 1 380px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .wide { flex: 1 1 100%; }
  .three { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .line { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .grow { flex: 1; }
  .nowrap { white-space: nowrap; }
  .editor { border-top: 1px solid var(--line); padding-top: 12px; display: flex; flex-direction: column; gap: 10px; }
  .x { background: none; border: 0; color: var(--muted); cursor: pointer; padding: 0 3px; font-size: 11px; }
  .x:hover { color: var(--fg); }
  .picon { display: flex; width: 20px; height: 20px; color: var(--accent-text); }
  .seg { display: inline-flex; align-self: flex-start; border: 1px solid var(--line-2); border-radius: 7px; overflow: hidden; }
  .seg button { padding: 7px 14px; background: none; border: 0; color: var(--muted); font-weight: 600; cursor: pointer; }
  .seg button.on { background: var(--select); color: var(--fg); }
  .picon :global(svg) { width: 20px; height: 20px; }
</style>
