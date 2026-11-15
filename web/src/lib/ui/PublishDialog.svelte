<script lang="ts">
  import { api, ApiError, vname, type Entity, type Version, type VersionPick } from '../api'
  import { app, say } from '../state.svelte'
  import Modal from './Modal.svelte'

  // A new version (published file) of one of the entity's tasks: an empty .blend made by the server's Blender,
  // a copy of another version, or a file from this computer (uploaded, so it also works with a remote server).
  let { entity, taskId = null, onclose }: { entity: Entity; taskId?: number | null; onclose: () => void } = $props()

  let task = $state<number | null>(null)
  let variant = $state('base')
  let mode = $state<'empty' | 'copy' | 'upload'>('empty')
  let source = $state<number | null>(null)
  let file = $state<FileList | null>(null)
  let description = $state('')
  let uses = $state<number[]>([])
  let busy = $state(false)
  let all = $state<VersionPick[]>([])
  const tasks = $derived(entity.tasks.filter((t) => t.enabled))
  const assetVersions = $derived(all.filter((v) => v.entity_kind === 'asset' && v.kind === 'blend'))

  $effect(() => {
    task = taskId ?? tasks[0]?.id ?? null
    api.get<VersionPick[]>(`/projects/${app.project!.id}/versions`).then((v) => (all = v))
  })

  async function publish(e: Event) {
    e.preventDefault()
    if (!task) return
    busy = true
    try {
      let v: Version
      if (mode === 'upload') {
        if (!file?.[0]) throw new ApiError('Choose a file')
        const form = new FormData()
        form.append('task_id', String(task))
        form.append('variant', variant)
        form.append('description', description)
        form.append('file', file[0])
        v = await api.post<Version>(`/entities/${entity.id}/versions/upload`, form)
        if (uses.length) await api.patch(`/versions/${v.id}`, { uses })
      } else {
        v = await api.post<Version>(`/entities/${entity.id}/versions`, { task_id: task, variant, mode, source_id: source, description, uses })
      }
      say(`Published ${entity.name} ${vname(v)}`)
      onclose()
    } catch (err) {
      say(err instanceof ApiError ? err.message : String(err), true)
    } finally {
      busy = false
    }
  }
</script>

<Modal title={`Publish · ${entity.name}`} {onclose} width="560px">
  <form class="form" onsubmit={publish}>
    <div class="row">
      <label class="stack">Task<select class="field" bind:value={task}>{#each tasks as t}<option value={t.id}>{t.name}</option>{/each}</select></label>
      <label class="stack">Variant<input class="field" bind:value={variant} pattern="[a-z0-9]+(_[a-z0-9]+)*" required /></label>
    </div>
    <span class="label">Content</span>
    <label class="check"><input type="radio" bind:group={mode} value="empty" /> An empty Blender file (made by Blender on the server)</label>
    <label class="check"><input type="radio" bind:group={mode} value="copy" /> A copy of a version</label>
    {#if mode === 'copy'}
      <select class="field" bind:value={source} required>
        <option value={null} disabled>Pick a version</option>
        {#each all as v}<option value={v.id}>{v.entity} · {vname(v)} · {v.kind}</option>{/each}
      </select>
    {/if}
    <label class="check"><input type="radio" bind:group={mode} value="upload" /> A file from this computer (any format)</label>
    {#if mode === 'upload'}<input class="field" type="file" bind:files={file} />{/if}
    <label class="stack">Description<input class="field" bind:value={description} placeholder="What this version is" /></label>
    <label class="stack">Uses (asset versions linked in it)
      <select class="field" multiple size="4" bind:value={uses}>
        {#each assetVersions as v}<option value={v.id}>{v.entity} · {vname(v)}</option>{/each}
      </select>
    </label>
    <div class="actions"><button type="button" class="btn ghost" onclick={onclose}>Cancel</button><button class="btn primary" disabled={busy}>{busy ? 'Publishing…' : 'Publish'}</button></div>
  </form>
</Modal>

<style>
  .form { display: flex; flex-direction: column; gap: 10px; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
