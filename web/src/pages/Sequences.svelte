<script lang="ts">
  import { api, type EntityRow, type Sequence } from '../lib/api'
  import { act, app, deleteEntity, go } from '../lib/state.svelte'
  import NewEntity from '../lib/ui/NewEntity.svelte'
  import Thumb from '../lib/ui/Thumb.svelte'

  // Sequences: the ordered list on the left (add, reorder), the selected one on the right (rename, describe,
  // delete) with its shots (create, delete). "No sequence" holds the shots without one.
  let sequences = $state<Sequence[]>([])
  let shots = $state<EntityRow[]>([])
  let picked = $state<number | null>(null)
  let newSeq = $state('')
  let form = $state({ name: '', description: '' })
  let creating = $state(false)
  const pid = $derived(app.project!.id)

  $effect(() => {
    void app.rev
    api.get<Sequence[]>(`/projects/${pid}/sequences`).then((s) => {
      sequences = s
      if (picked !== null && !s.some((x) => x.id === picked)) picked = null
      if (picked === null && s[0]) picked = s[0].id
    })
    api.get<EntityRow[]>(`/projects/${pid}/entities?kind=shot`).then((r) => (shots = r))
  })

  const current = $derived(sequences.find((s) => s.id === picked) ?? null)
  const inSeq = (id: number | null) => shots.filter((r) => r.sequence_id === id)
  const done = (rs: EntityRow[]) => {
    const all = rs.flatMap((r) => r.tasks.filter((t) => t.enabled))
    return all.length ? Math.round((100 * all.filter((t) => t.status === 'app' || t.status === 'skip').length) / all.length) : 0
  }
  $effect(() => { form = { name: current?.name ?? '', description: current?.description ?? '' } })

  async function addSeq(e: Event) {
    e.preventDefault()
    const s = await act(() => api.post<Sequence>(`/projects/${pid}/sequences`, { name: newSeq }), `Sequence ${newSeq} added`)
    if (s) { newSeq = ''; picked = s.id }
  }
  const save = (e: Event) => {
    e.preventDefault()
    act(() => api.patch(`/sequences/${current!.id}`, { name: form.name, description: form.description }), 'Sequence saved')
  }
  const move = (i: number, d: number) => {
    const list = [...sequences]
    const [s] = list.splice(i, 1)
    list.splice(i + d, 0, s)
    list.forEach((x, n) => api.patch(`/sequences/${x.id}`, { name: x.name, description: x.description, sort: n }))
  }
  const remove = (s: Sequence) =>
    confirm(`Delete the sequence ${s.name}? Its ${s.shot_count} shots are kept, without a sequence.`) &&
    act(() => api.del(`/sequences/${s.id}`), `Sequence ${s.name} deleted`)
</script>

<div class="page">
  <div class="toolbar">
    <h1>Sequences</h1><span class="muted">{sequences.length} sequences · {shots.length} shots</span>
    <form class="add" onsubmit={addSeq}><input class="field" bind:value={newSeq} placeholder="New sequence, e.g. Intro" aria-label="New sequence name" required /><button class="btn primary">+ Sequence</button></form>
  </div>
  <div class="cols">
    <nav class="list" aria-label="Sequences">
      {#each sequences as s, i (s.id)}
        <div class="seq" class:sel={picked === s.id}>
          <button class="pick" onclick={() => (picked = s.id)} aria-current={picked === s.id}>
            <b class="ell">{s.name}</b><span class="muted small">{s.shot_count} shots</span>
            <span class="bar"><span style:width={done(inSeq(s.id)) + '%'} style:background="var(--ok)"></span></span>
          </button>
          <button class="btn ghost small" disabled={i === 0} onclick={() => move(i, -1)} aria-label={`Move ${s.name} up`}>↑</button>
          <button class="btn ghost small" disabled={i === sequences.length - 1} onclick={() => move(i, 1)} aria-label={`Move ${s.name} down`}>↓</button>
        </div>
      {/each}
      <div class="seq" class:sel={picked === -1}>
        <button class="pick" onclick={() => (picked = -1)} aria-current={picked === -1}>
          <i class="soft">No sequence</i><span class="muted small">{inSeq(null).length} shots</span><span></span>
        </button>
      </div>
    </nav>

    <section class="detail">
      {#if current}
        <form class="panel box" onsubmit={save}>
          <div class="line"><label class="stack grow">Name<input class="field" bind:value={form.name} required /></label></div>
          <label class="stack">Description<textarea class="field" rows="2" bind:value={form.description}></textarea></label>
          <div class="line">
            <button class="btn primary" disabled={form.name === current.name && form.description === current.description}>Save</button>
            <button type="button" class="btn ghost danger right" onclick={() => remove(current!)}>Delete sequence</button>
          </div>
        </form>
      {/if}
      {#if current || picked === -1}
        {@const rows = inSeq(current?.id ?? null)}
        <div class="line"><b>{rows.length} shots</b><button class="btn right" onclick={() => (creating = true)}>+ Shot</button></div>
        <table class="grid">
          <thead><tr><th></th><th>Shot</th><th>Cut</th><th>Done</th><th></th></tr></thead>
          <tbody>
            {#each rows as r (r.id)}
              <tr class="row" ondblclick={() => go(`entity/${r.id}`)}>
                <td><Thumb item={r} /></td>
                <td><a class="name" href={`#/entity/${r.id}`}>{r.name}</a><div class="muted small">{r.title}</div></td>
                <td class="mono soft small">{r.cut_in}–{r.cut_out}</td>
                <td><span class="bar small-bar"><span style:width={done([r]) + '%'} style:background="var(--ok)"></span></span></td>
                <td class="end"><button class="btn ghost small danger" onclick={() => deleteEntity(r)}>Delete</button></td>
              </tr>
            {:else}<tr><td colspan="5" class="muted">No shot in this sequence.</td></tr>{/each}
          </tbody>
        </table>
      {:else}<p class="empty">No sequence yet: add one above.</p>{/if}
    </section>
  </div>
</div>
{#if creating}<NewEntity kind="shot" sequenceId={current?.id ?? null} onclose={() => (creating = false)} />{/if}

<style>
  .page { padding: 12px 18px 18px; }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 12px; }
  h1 { font-size: 22px; }
  .add { display: flex; gap: 8px; margin-left: auto; }
  .cols { display: flex; gap: 18px; align-items: flex-start; flex-wrap: wrap; }
  .list { flex: 0 0 340px; display: flex; flex-direction: column; gap: 4px; }
  .seq { display: flex; align-items: center; gap: 2px; border-radius: 8px; }
  .seq.sel { background: var(--hover); }
  .pick { flex: 1; min-width: 0; display: grid; grid-template-columns: 1fr 60px 64px; align-items: center; gap: 8px; padding: 8px 10px; border: 0; background: none; color: var(--fg); text-align: left; cursor: pointer; border-radius: 8px; }
  .pick:hover { background: var(--hover-soft); }
  .ell { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .detail { flex: 1; min-width: 320px; display: flex; flex-direction: column; gap: 12px; }
  .box { padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .line { display: flex; align-items: center; gap: 8px; }
  .grow { flex: 1; }
  .right { margin-left: auto; }
  .small-bar { width: 90px; }
  .name { color: var(--fg); font-weight: 700; text-decoration: none; }
  .end { text-align: right; }
</style>
