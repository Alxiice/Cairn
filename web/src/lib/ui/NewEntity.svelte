<script lang="ts">
  import { api, type Entity, type Sequence, type Template } from '../api'
  import { act, app, go } from '../state.svelte'
  import Modal from './Modal.svelte'

  // New shot or asset: name, its group, and the task template it starts with (the project default first).
  let { kind, onclose, sequenceId = null, assetType = '' }:
    { kind: 'shot' | 'asset'; onclose: () => void; sequenceId?: number | null; assetType?: string } = $props()

  let name = $state('')
  let title = $state('')
  let seq = $state<number | null>(null)
  let type = $state('')
  let head = $state(1)
  let tail = $state(240)
  let templateId = $state<number | null>(null)
  let sequences = $state<Sequence[]>([])
  let templates = $state<Template[]>([])
  const pid = $derived(app.project!.id)
  const ofKind = $derived(templates.filter((t) => t.kind === kind))
  const tasks = $derived(ofKind.find((t) => t.id === templateId)?.tasks ?? [])

  $effect(() => {
    seq = sequenceId
    type = assetType || app.project!.asset_types[0] || ''
    api.get<Sequence[]>(`/projects/${pid}/sequences`).then((s) => (sequences = s))
    api.get<Template[]>(`/projects/${pid}/templates`).then((t) => {
      templates = t
      templateId = app.project![kind === 'shot' ? 'default_shot_template' : 'default_asset_template']
    })
  })

  async function create(e: Event) {
    e.preventDefault()
    const body = kind === 'shot'
      ? { kind, name, title, sequence_id: seq, head, tail, template_id: templateId }
      : { kind, name, title, asset_type: type, template_id: templateId }
    const made = await act(() => api.post<Entity>(`/projects/${pid}/entities`, body), `${name} created`)
    if (made) { onclose(); go(`entity/${made.id}`) }
  }
</script>

<Modal title={kind === 'shot' ? 'New shot' : 'New asset'} {onclose}>
  <form class="form" onsubmit={create}>
    <label class="stack">Name<input class="field" bind:value={name} placeholder={kind === 'shot' ? 'sh030' : 'quantum_moon'} pattern="[a-z0-9]+(_[a-z0-9]+)*" required /></label>
    <label class="stack">Title<input class="field" bind:value={title} placeholder="optional" /></label>
    {#if kind === 'shot'}
      <label class="stack">Sequence
        <select class="field" bind:value={seq}><option value={null}>No sequence</option>{#each sequences as s}<option value={s.id}>{s.name}</option>{/each}</select>
      </label>
      <div class="row"><label class="stack">Head<input class="field" type="number" bind:value={head} /></label><label class="stack">Tail<input class="field" type="number" bind:value={tail} /></label></div>
    {:else}
      <label class="stack">Type
        <select class="field" bind:value={type}>{#each app.project!.asset_types as t}<option value={t}>{t}</option>{/each}</select>
      </label>
    {/if}
    <label class="stack">Task template
      <select class="field" bind:value={templateId}>{#each ofKind as t}<option value={t.id}>{t.name}</option>{/each}</select>
    </label>
    <div class="tasks">{#each tasks as t}<span class="tag">{t}</span>{:else}<span class="muted small">No task</span>{/each}</div>
    <p class="muted small">Tasks can be added, removed or replaced by another template later, on the {kind}'s page.</p>
    <div class="actions"><button type="button" class="btn ghost" onclick={onclose}>Cancel</button><button class="btn primary">Create</button></div>
  </form>
</Modal>

<style>
  .form { display: flex; flex-direction: column; gap: 10px; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .tasks { display: flex; flex-wrap: wrap; gap: 6px; }
  .actions { display: flex; justify-content: flex-end; gap: 8px; }
  p { margin: 0; }
</style>
