<script lang="ts">
  import { api, statusLabel, STATUSES, type EntityRow, type Status } from '../lib/api'
  import { app, deleteEntity } from '../lib/state.svelte'
  import EntityDrawer from '../lib/ui/EntityDrawer.svelte'
  import NewEntity from '../lib/ui/NewEntity.svelte'
  import Thumb from '../lib/ui/Thumb.svelte'

  // The asset library: facets on the left, big cards, the side panel.
  let rows = $state<EntityRow[]>([])
  let selected = $state<number | null>(null)
  let text = $state('')
  let types = $state<string[]>([])
  let statuses = $state<string[]>([])
  let tasks = $state<string[]>([])
  let use = $state<'' | 'used' | 'unused'>('')
  let size = $state(200)
  const MIN = 150 // the slider at its minimum shows a list instead of cards
  let creating = $state(false)

  $effect(() => {
    void app.rev
    api.get<EntityRow[]>(`/projects/${app.project!.id}/entities?kind=asset`).then((r) => {
      rows = r
      if (selected && !r.some((x) => x.id === selected)) selected = null // deleted
    })
  })

  /** An asset's overall status: the least advanced of its enabled tasks. */
  const order: Status[] = ['ret', 'ns', 'wip', 'rev', 'app', 'skip']
  const overall = (r: EntityRow): Status => {
    const st = r.tasks.filter((t) => t.enabled).map((t) => t.status)
    if (!st.length) return 'ns'
    if (st.every((s) => s === 'ns')) return 'ns'
    if (st.every((s) => s === 'app' || s === 'skip')) return 'app'
    return order.find((o) => o !== 'ns' && st.includes(o)) ?? 'wip'
  }
  const taskNames = $derived([...new Set(rows.flatMap((r) => r.tasks.filter((t) => t.enabled).map((t) => t.name)))])
  const shown = $derived(rows.filter((r) =>
    (!text || (r.name + ' ' + r.title + ' ' + r.description).toLowerCase().includes(text.toLowerCase())) &&
    (!types.length || types.includes(r.asset_type)) &&
    (!statuses.length || statuses.includes(overall(r))) &&
    (!tasks.length || tasks.every((n) => r.tasks.some((t) => t.enabled && t.name === n))) &&
    (!use || (use === 'used' ? r.used_in > 0 : r.used_in === 0))))
  const count = (f: (r: EntityRow) => boolean) => rows.filter(f).length
</script>

<div class="layout">
  <aside class="facets">
    <span class="label">Type</span>
    {#each app.project!.asset_types as t}
      <label class="check"><input type="checkbox" bind:group={types} value={t} /> <span class="grow">{t}</span><span class="mono muted small">{count((r) => r.asset_type === t)}</span></label>
    {/each}
    <span class="label">Status</span>
    {#each STATUSES.filter((s) => s.id !== 'skip') as s}
      <label class="check"><input type="checkbox" bind:group={statuses} value={s.id} /> <span class="grow">{s.label}</span><span class="mono muted small">{count((r) => overall(r) === s.id)}</span></label>
    {/each}
    <span class="label">Has the task</span>
    {#each taskNames as n}
      <label class="check"><input type="checkbox" bind:group={tasks} value={n} /> <span class="grow">{n}</span><span class="mono muted small">{count((r) => r.tasks.some((t) => t.enabled && t.name === n))}</span></label>
    {/each}
    <span class="label">Used</span>
    <label class="check"><input type="radio" bind:group={use} value="" /> Any</label>
    <label class="check"><input type="radio" bind:group={use} value="used" /> <span class="grow">In a shot or asset</span><span class="mono muted small">{count((r) => r.used_in > 0)}</span></label>
    <label class="check"><input type="radio" bind:group={use} value="unused" /> <span class="grow">Unused</span><span class="mono muted small">{count((r) => r.used_in === 0)}</span></label>
  </aside>
  <div class="content">
    <div class="toolbar">
      <h1>Assets</h1><span class="muted">{shown.length} of {rows.length}</span>
      <input class="field" bind:value={text} placeholder="Filter assets…" aria-label="Filter assets" />
      <label class="check">Size <input type="range" min={MIN} max="320" bind:value={size} aria-label="Thumbnail size" /></label>
      <button class="btn primary right" onclick={() => (creating = true)}>+ Asset</button>
    </div>
    {#if size <= MIN}
      <div class="scroll"><table class="grid">
        <thead><tr><th></th><th>Asset</th><th>Type</th><th>Status</th><th>Used</th><th></th></tr></thead>
        <tbody>
          {#each shown as r (r.id)}
            <tr class="row" class:sel={selected === r.id} onclick={() => (selected = r.id)} ondblclick={() => (location.hash = `#/entity/${r.id}`)}>
              <td><Thumb item={r} /></td>
              <td><b>{r.name}</b><div class="muted small ell">{r.title || r.description}</div></td>
              <td><span class="tag">{r.asset_type}</span></td>
              <td><span class="pill {overall(r)}">{statusLabel(overall(r))}</span></td>
              <td class="muted small">{r.used_in ? `in ${r.used_in}` : 'unused'}</td>
              <td class="end"><button class="btn ghost small danger" onclick={(e) => { e.stopPropagation(); deleteEntity(r) }}>Delete</button></td>
            </tr>
          {/each}
        </tbody>
      </table></div>
    {:else}
    <div class="cards" style:grid-template-columns={`repeat(auto-fill, minmax(${size}px, 1fr))`}>
      {#each shown as r (r.id)}
        <button class="card" class:sel={selected === r.id} onclick={() => (selected = r.id)} ondblclick={() => (location.hash = `#/entity/${r.id}`)}>
          <Thumb item={r} width="100%" height={Math.round(size * 0.6) + 'px'} />
          <span class="line"><b>{r.name}</b><span class="tag right">{r.asset_type}</span></span>
          <span class="muted small ell">{r.title || r.description || '—'}</span>
          <span class="line"><span class="pill {overall(r)}">{statusLabel(overall(r))}</span><span class="muted small right">{r.used_in ? `used in ${r.used_in}` : 'unused'}</span></span>
        </button>
      {/each}
    </div>
    {/if}
    {#if !rows.length}<p class="empty">No asset yet: “+ Asset”.</p>{/if}
  </div>
  {#if selected}{#key selected}<EntityDrawer id={selected} onclose={() => (selected = null)} />{/key}{/if}
</div>
{#if creating}<NewEntity kind="asset" assetType={types[0] ?? ''} onclose={() => (creating = false)} />{/if}

<style>
  .layout { display: flex; min-height: 100%; }
  .facets { flex: 0 0 200px; padding: 14px 16px; border-right: 1px solid var(--line-soft); display: flex; flex-direction: column; gap: 6px; }
  .facets .label { margin-top: 10px; }
  .grow { flex: 1; }
  .content { flex: 1; min-width: 0; }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 12px 18px; }
  h1 { font-size: 22px; }
  .right { margin-left: auto; }
  .cards { display: grid; gap: 12px; padding: 0 18px 18px; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 8px; display: flex; flex-direction: column; gap: 6px; text-align: left; color: var(--fg); cursor: pointer; }
  .card:hover { border-color: var(--line-2); }
  .card.sel { border-color: var(--accent); background: var(--hover); }
  .line { display: flex; align-items: center; gap: 6px; }
  .scroll { padding: 0 18px 18px; overflow-x: auto; }
  .end { text-align: right; }
  .ell { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
