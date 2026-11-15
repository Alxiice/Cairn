<script lang="ts">
  import { ago, api, type EntityRow, type Sequence } from '../lib/api'
  import { app, go } from '../lib/state.svelte'
  import EntityDrawer from '../lib/ui/EntityDrawer.svelte'
  import NewEntity from '../lib/ui/NewEntity.svelte'
  import StatusSelect from '../lib/ui/StatusSelect.svelte'
  import Thumb from '../lib/ui/Thumb.svelte'

  // The tracker table: one row per shot, grouped by sequence, one column per task (status and latest version).
  let rows = $state<EntityRow[]>([])
  let sequences = $state<Sequence[]>([])
  let selected = $state<number | null>(null)
  let folded = $state<Record<string, boolean>>({})
  let hideApproved = $state(false)
  let filter = $state('')
  let creating = $state(false)

  $effect(() => {
    void app.rev
    const pid = app.project!.id
    api.get<EntityRow[]>(`/projects/${pid}/entities?kind=shot`).then((r) => (rows = r))
    api.get<Sequence[]>(`/projects/${pid}/sequences`).then((s) => (sequences = s))
  })

  // columns: every task name in use, in the order they first appear
  const columns = $derived([...new Set(rows.flatMap((r) => r.tasks.filter((t) => t.enabled).map((t) => t.name)))])
  const shown = $derived(rows.filter((r) =>
    (!filter || (r.name + ' ' + r.title).toLowerCase().includes(filter.toLowerCase())) &&
    (!hideApproved || r.tasks.some((t) => t.enabled && !['app', 'skip'].includes(t.status)))))
  const groups = $derived([
    ...sequences.map((s) => ({ key: String(s.id), id: s.id as number | null, name: s.name, rows: shown.filter((r) => r.sequence_id === s.id) })),
    { key: 'none', id: null, name: 'No sequence', rows: shown.filter((r) => r.sequence_id === null) },
  ].filter((g) => g.rows.length || (g.id !== null && !filter)))
  const done = (rs: EntityRow[]) => {
    const all = rs.flatMap((r) => r.tasks.filter((t) => t.enabled))
    return all.length ? Math.round((100 * all.filter((t) => t.status === 'app' || t.status === 'skip').length) / all.length) : 0
  }
  const cell = (r: EntityRow, name: string) => r.tasks.find((t) => t.name === name && t.enabled)
</script>

<div class="layout">
  <div class="content">
    <div class="toolbar">
      <h1>Shots</h1><span class="muted">{rows.length} shots · {sequences.length} sequences</span>
      <input class="field" bind:value={filter} placeholder="Filter shots…" aria-label="Filter shots" />
      <label class="check"><input type="checkbox" bind:checked={hideApproved} /> Hide finished</label>
      <button class="btn primary right" onclick={() => (creating = true)}>+ Shot</button>
    </div>
    <div class="scroll">
      <table class="grid">
        <thead><tr><th></th><th>Shot</th><th>Cut</th>{#each columns as c}<th>{c}</th>{/each}<th>Notes</th><th>Updated</th></tr></thead>
        <tbody>
          {#each groups as g (g.key)}
            <tr class="group"><td colspan={columns.length + 5}>
              <div class="ghead">
                <button class="btn ghost small gname" onclick={() => (folded[g.key] = !folded[g.key])} aria-expanded={!folded[g.key]} title={g.name}>{folded[g.key] ? '▸' : '▾'} <b>{g.name}</b></button>
                <span class="muted small gcount">{g.rows.length} shots</span>
                <div class="bar gbar"><div style:width={done(g.rows) + '%'} style:background="var(--ok)"></div></div>
                <span class="mono muted small gpct">{done(g.rows)}%</span>
              </div>
            </td></tr>
            {#if !folded[g.key]}
              {#each g.rows as r (r.id)}
                <tr class="row" class:sel={selected === r.id} onclick={() => (selected = r.id)} ondblclick={() => go(`entity/${r.id}`)}>
                  <td><Thumb item={r} /></td>
                  <td><a class="name" href={`#/entity/${r.id}`} onclick={(e) => e.stopPropagation()}>{r.name}</a><div class="muted small">{r.title}</div></td>
                  <td class="mono soft small">{r.cut_in}–{r.cut_out}</td>
                  {#each columns as c}
                    {@const t = cell(r, c)}
                    <td>{#if t}<StatusSelect status={t.status} onchange={(s) => api.patch(`/tasks/${t.id}`, { status: s })} />{#if t.latest}<span class="mono muted small v">v{String(t.latest).padStart(3, '0')}</span>{/if}{:else}<span class="muted">—</span>{/if}</td>
                  {/each}
                  <td>{#if r.open_notes}<span class="tag">{r.open_notes} open</span>{:else}<span class="muted">—</span>{/if}</td>
                  <td class="muted small nowrap">{ago(r.updated_at)}</td>
                </tr>
              {/each}
            {/if}
          {/each}
        </tbody>
      </table>
      {#if !rows.length}<p class="empty">No shot yet. Add sequences on the Sequences page, then “+ Shot”.</p>{/if}
    </div>
  </div>
  {#if selected}{#key selected}<EntityDrawer id={selected} onclose={() => (selected = null)} />{/key}{/if}
</div>
{#if creating}<NewEntity kind="shot" onclose={() => (creating = false)} />{/if}

<style>
  .layout { display: flex; min-height: 100%; }
  .content { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 12px 18px; }
  h1 { font-size: 22px; }
  .right { margin-left: auto; }
  .scroll { padding: 0 18px 18px; overflow-x: auto; }
  tr.group td { background: var(--group); padding: 6px 8px; }
  .ghead { display: flex; align-items: center; gap: 10px; }
  .gname { flex: 0 0 220px; justify-content: flex-start; overflow: hidden; white-space: nowrap; }
  .gname b { overflow: hidden; text-overflow: ellipsis; }
  .gcount { flex: 0 0 64px; }
  .gbar { width: 140px; }
  .gpct { width: 40px; }
  .name { color: var(--fg); font-weight: 700; text-decoration: none; }
  .v { margin-left: 6px; }
  .nowrap { white-space: nowrap; }
</style>
