<script lang="ts">
  import { ago, api, vname, vnum, type Entity, type EntityRow, type LinkRef, type Note, type Sequence, type Template, type Version } from '../lib/api'
  import { openInBlender, uploadThumbnail } from '../lib/actions'
  import { act, app } from '../lib/state.svelte'
  import NoteDialog from '../lib/ui/NoteDialog.svelte'
  import PublishDialog from '../lib/ui/PublishDialog.svelte'
  import StatusSelect from '../lib/ui/StatusSelect.svelte'
  import Thumb from '../lib/ui/Thumb.svelte'

  // The page of a shot or an asset: its task pipeline (editable), its versions, notes, what it uses and where it is used.
  let { id }: { id: number } = $props()
  let e = $state<Entity | null>(null)
  let versions = $state<Version[]>([])
  let notes = $state<Note[]>([])
  let templates = $state<Template[]>([])
  let sequences = $state<Sequence[]>([])
  let assets = $state<EntityRow[]>([])
  let tab = $state<'versions' | 'notes' | 'uses' | 'used'>('versions')
  let taskFilter = $state<number | null>(null)
  let latestOnly = $state(false)
  let newTask = $state('')
  let publishing = $state<{ task: number | null } | null>(null)
  let noting = $state<LinkRef[] | null>(null)
  let form = $state<Record<string, unknown>>({})
  let dirty = $state(false)

  $effect(() => {
    void app.rev
    const pid = app.project!.id
    api.get<Entity>(`/entities/${id}`).then((x) => {
      e = x
      if (!dirty) form = { title: x.title, description: x.description, sequence_id: x.sequence_id, asset_type: x.asset_type,
                           head: x.head, tail: x.tail, cut_in: x.cut_in, cut_out: x.cut_out }
    })
    api.get<Version[]>(`/entities/${id}/versions`).then((v) => (versions = v))
    api.get<Note[]>(`/projects/${pid}/notes?target=entity&target_id=${id}`).then((n) => (notes = n))
    api.get<Template[]>(`/projects/${pid}/templates`).then((t) => (templates = t))
    api.get<Sequence[]>(`/projects/${pid}/sequences`).then((s) => (sequences = s))
    api.get<EntityRow[]>(`/projects/${pid}/entities?kind=asset`).then((a) => (assets = a))
  })

  const shown = $derived(versions.filter((v) => (!taskFilter || v.task_id === taskFilter) &&
    (!latestOnly || !versions.some((o) => o.task_id === v.task_id && o.variant === v.variant && o.number > v.number))))
  const canUse = $derived(assets.filter((a) => a.id !== id && !e?.uses.some((u) => u.id === a.id)))

  async function save() {
    const body = e!.kind === 'shot'
      ? { title: form.title, description: form.description, sequence_id: form.sequence_id, head: form.head, tail: form.tail, cut_in: form.cut_in, cut_out: form.cut_out }
      : { title: form.title, description: form.description, asset_type: form.asset_type }
    if (await act(() => api.patch(`/entities/${id}`, body), 'Saved')) dirty = false
  }
  const addTask = async (ev: Event) => {
    ev.preventDefault()
    if (await act(() => api.post(`/entities/${id}/tasks`, { name: newTask.trim() }))) newTask = ''
  }
  const applyTemplate = (tid: number) => {
    const t = templates.find((x) => x.id === tid)!
    if (confirm(`Apply the ${t.name} template? Tasks it does not list are removed (or disabled when they have versions); custom tasks stay.`))
      act(() => api.post(`/entities/${id}/apply-template`, { template_id: tid }), `${t.name} applied`)
  }
  const removeTask = (tid: number, name: string, count: number) => {
    if (confirm(count ? `${name} has versions: it will be disabled (hidden, history kept). Continue?` : `Remove the ${name} task?`))
      act(() => api.del(`/tasks/${tid}`))
  }
  const pickThumb = (ev: Event) => {
    const f = (ev.currentTarget as HTMLInputElement).files?.[0]
    if (f) uploadThumbnail(id, f)
  }
</script>

{#if e}
  <div class="page">
    <div class="hero">
      <label class="thumbpick" title="Set the thumbnail"><Thumb item={e} width="160px" height="90px" /><input type="file" accept="image/png,image/jpeg,image/webp" onchange={pickThumb} /></label>
      <div class="who">
        <div class="line"><h1>{e.name}</h1><span class="tag">{e.kind === 'shot' ? e.sequence ?? 'no sequence' : e.asset_type}</span></div>
        <span class="soft">{e.title || (e.kind === 'shot' ? 'Shot' : 'Asset')} · updated {ago(e.updated_at)}</span>
      </div>
      <div class="acts">
        <button class="btn" onclick={() => (noting = [{ target: 'entity', id: e!.id, label: e!.name }])}>+ Note</button>
        <a class="btn" href={`#/review?entity=${e.id}`}>Review</a>
        <button class="btn primary" onclick={() => (publishing = { task: null })}>Publish…</button>
      </div>
    </div>

    <div class="strip">
      {#each e.tasks as t, i (t.id)}
        <div class="step" class:off={!t.enabled}>
          <div class="line"><b>{t.name}</b>{#if t.custom}<span class="tag">custom</span>{/if}<span class="mono muted small right">{vnum(t.latest)}</span></div>
          {#if t.enabled}
            <StatusSelect status={t.status} onchange={(s) => api.patch(`/tasks/${t.id}`, { status: s })} />
            <div class="line small"><span class="muted">{t.version_count} version{t.version_count === 1 ? '' : 's'}</span>
              <button class="btn ghost small right" onclick={() => (publishing = { task: t.id })} aria-label={`Publish ${t.name}`}>+</button>
              <button class="btn ghost small" onclick={() => removeTask(t.id, t.name, t.version_count)} aria-label={`Remove ${t.name}`}>✕</button></div>
          {:else}
            <span class="muted small">disabled · {t.version_count} versions kept</span>
            <button class="btn small" onclick={() => api.patch(`/tasks/${t.id}`, { enabled: true })}>Enable</button>
          {/if}
        </div>
        {#if i < e.tasks.length - 1}<span class="arrow" aria-hidden="true">→</span>{/if}
      {/each}
      <div class="step add">
        <form onsubmit={addTask}><input class="field" bind:value={newTask} placeholder="+ custom task" pattern="[a-z0-9]+(_[a-z0-9]+)*" aria-label="New task name" /></form>
        <select class="field" value="" onchange={(ev) => { const v = Number((ev.currentTarget as HTMLSelectElement).value); (ev.currentTarget as HTMLSelectElement).value = ''; if (v) applyTemplate(v) }} aria-label="Apply a task template">
          <option value="">Apply a template…</option>
          {#each templates.filter((t) => t.kind === e!.kind) as t}<option value={t.id}>{t.name}: {t.tasks.join(', ')}</option>{/each}
        </select>
      </div>
    </div>

    <div class="body">
      <div class="main">
        <nav class="tabs" aria-label="Sections">
          {#each [['versions', `Versions ${versions.length}`], ['notes', `Notes ${notes.length}`], ['uses', `${e.kind === 'shot' ? 'Assets' : 'Uses'} ${e.uses.length}`], ['used', `Used in ${e.used_in.length}`]] as [k, label]}
            {#if !(k === 'used' && e.kind === 'shot')}<button class:on={tab === k} onclick={() => (tab = k as typeof tab)}>{label}</button>{/if}
          {/each}
        </nav>
        {#if tab === 'versions'}
          <div class="line filters">
            <select class="field" bind:value={taskFilter} aria-label="Task"><option value={null}>All tasks</option>{#each e.tasks as t}<option value={t.id}>{t.name}</option>{/each}</select>
            <label class="check"><input type="checkbox" bind:checked={latestOnly} /> Latest only</label>
          </div>
          <table class="grid">
            <thead><tr><th>Version</th><th>Task</th><th>Variant</th><th>Kind</th><th>Description</th><th>By</th><th>Date</th><th></th></tr></thead>
            <tbody>
              {#each shown as v (v.id)}
                <tr>
                  <td class="mono"><b>{vnum(v.number)}</b></td><td>{v.task}</td><td><span class="tag">{v.variant}</span></td><td><span class="tag">{v.kind}</span></td>
                  <td class="soft small">{v.description}</td><td class="muted small">{v.origin}</td><td class="muted small nowrap">{ago(v.created_at)}</td>
                  <td class="nowrap">
                    <button class="btn ghost small" onclick={() => openInBlender(v.id)}>{v.kind === 'blend' ? 'Open in Blender' : 'Open'}</button>
                    <a class="btn ghost small" href={`#/review?entity=${e.id}&a=${v.id}`}>Review</a>
                    <button class="btn ghost small" onclick={() => (noting = [{ target: 'entity', id: e!.id, label: e!.name }, { target: 'version', id: v.id, label: `${e!.name} · ${vname(v)}` }])}>Note</button>
                  </td>
                </tr>
              {:else}<tr><td colspan="8" class="empty">Nothing published yet: “Publish…”.</td></tr>{/each}
            </tbody>
          </table>
        {:else if tab === 'notes'}
          {#each notes as n (n.id)}
            <a class="note panel" href={`#/notes/${n.id}`}>
              <div class="line"><b>{n.title}</b><span class="pill {n.status === 'open' ? 'wip' : 'app'}">{n.status}</span><span class="muted small right">{ago(n.updated_at)}</span></div>
              <span class="soft small">{n.content}</span>
              <div class="line">{#each n.links as l}<span class="tag">{l.label}</span>{/each}<span class="muted small right">{n.reply_count} replies</span></div>
            </a>
          {:else}<p class="empty">No note on this {e.kind}.</p>{/each}
        {:else if tab === 'uses'}
          <div class="refs">
            {#each e.uses as u (u.id)}<span class="tag"><a href={`#/entity/${u.id}`}>{u.name}</a> <button class="x" onclick={() => api.del(`/entities/${id}/uses/${u.id}`)} aria-label={`Remove ${u.name}`}>✕</button></span>{/each}
            <select class="field" value="" onchange={(ev) => { const v = Number((ev.currentTarget as HTMLSelectElement).value); if (v) act(() => api.post(`/entities/${id}/uses`, { child_id: v })) }} aria-label="Add an asset">
              <option value="">+ Add an asset…</option>{#each canUse as a}<option value={a.id}>{a.name} · {a.asset_type}</option>{/each}
            </select>
          </div>
        {:else}
          <div class="refs">{#each e.used_in as u (u.id)}<a class="tag" href={`#/entity/${u.id}`}>{u.kind} · {u.name}</a>{:else}<span class="muted">Not used yet.</span>{/each}</div>
        {/if}
      </div>

      <aside class="panel details">
        <span class="label">Details</span>
        <label class="stack">Title<input class="field" bind:value={form.title} oninput={() => (dirty = true)} /></label>
        <label class="stack">Description<textarea class="field" rows="3" bind:value={form.description} oninput={() => (dirty = true)}></textarea></label>
        {#if e.kind === 'shot'}
          <label class="stack">Sequence<select class="field" bind:value={form.sequence_id} onchange={() => (dirty = true)}><option value={null}>No sequence</option>{#each sequences as s}<option value={s.id}>{s.name}</option>{/each}</select></label>
          <div class="frames">
            {#each [['head', 'Head'], ['tail', 'Tail'], ['cut_in', 'Cut in'], ['cut_out', 'Cut out']] as [k, label]}
              <label class="stack">{label}<input class="field mono" type="number" bind:value={form[k]} oninput={() => (dirty = true)} /></label>
            {/each}
          </div>
          <span class="muted small">Head–tail: the animated range. Cut in–out: what stays in the edit and gets rendered.</span>
        {:else}
          <label class="stack">Type<select class="field" bind:value={form.asset_type} onchange={() => (dirty = true)}>{#each app.project!.asset_types as t}<option value={t}>{t}</option>{/each}</select></label>
        {/if}
        <button class="btn primary" disabled={!dirty} onclick={save}>Save</button>
      </aside>
    </div>
  </div>
  {#if publishing}<PublishDialog entity={e} taskId={publishing.task} onclose={() => (publishing = null)} />{/if}
  {#if noting}<NoteDialog links={noting} onclose={() => (noting = null)} />{/if}
{/if}

<style>
  .page { padding: 16px 18px; display: flex; flex-direction: column; gap: 14px; }
  .hero { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; }
  .thumbpick { position: relative; cursor: pointer; }
  .thumbpick input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
  .who { display: flex; flex-direction: column; gap: 4px; }
  h1 { font-size: 26px; }
  .acts { margin-left: auto; display: flex; gap: 8px; }
  .line { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .right { margin-left: auto; }
  .strip { display: flex; flex-wrap: wrap; gap: 8px; align-items: stretch; }
  .step { flex: 0 1 180px; background: var(--panel); border: 1px solid var(--line); border-radius: 9px; padding: 10px; display: flex; flex-direction: column; gap: 6px; }
  .step.off { opacity: .55; border-style: dashed; }
  .step.add { border-style: dashed; justify-content: center; }
  .arrow { align-self: center; color: var(--muted); }
  .body { display: flex; flex-wrap: wrap; gap: 14px; }
  .main { flex: 999 1 600px; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
  .tabs { display: flex; gap: 18px; border-bottom: 1px solid var(--line-soft); }
  .tabs button { background: none; border: 0; border-bottom: 2px solid transparent; padding: 8px 2px; color: var(--muted); font-weight: 600; cursor: pointer; }
  .tabs button.on { color: var(--fg); border-bottom-color: var(--accent); }
  .filters { gap: 12px; }
  .nowrap { white-space: nowrap; }
  .note { display: flex; flex-direction: column; gap: 6px; padding: 12px; color: var(--fg); text-decoration: none; margin-bottom: 8px; }
  .refs { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .refs a { color: inherit; text-decoration: none; }
  .x { background: none; border: 0; color: var(--muted); cursor: pointer; font-size: 10px; }
  .details { flex: 1 1 300px; padding: 14px; display: flex; flex-direction: column; gap: 10px; align-self: flex-start; }
  .frames { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
</style>
