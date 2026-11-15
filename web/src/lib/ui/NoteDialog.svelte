<script lang="ts">
  import { api, type LinkRef, type Note } from '../api'
  import { act, app, go } from '../state.svelte'
  import LinkPicker from './LinkPicker.svelte'
  import Modal from './Modal.svelte'

  // A new note, linked to what it is about (prefilled from where it was opened).
  let { links: initial = [], frame = null, onclose }: { links?: LinkRef[]; frame?: number | null; onclose: () => void } = $props()

  let title = $state('')
  let content = $state('')
  let links = $state<LinkRef[]>([])
  let assign = $state(true)
  $effect(() => { links = [...initial] })

  async function create(e: Event) {
    e.preventDefault()
    const n = await act(() => api.post<Note>(`/projects/${app.project!.id}/notes`, {
      title, content, frame, links: links.map(({ target, id }) => ({ target, id })), assignees: assign ? [1] : [],
    }), 'Note posted')
    if (n) { onclose(); go(`notes/${n.id}`) }
  }
</script>

<Modal title="New note" {onclose} width="560px">
  <form class="form" onsubmit={create}>
    <label class="stack">Title<input class="field" bind:value={title} required /></label>
    <label class="stack">Note<textarea class="field" rows="4" bind:value={content}></textarea></label>
    {#if frame !== null}<span class="tag">frame {frame}</span>{/if}
    <span class="label">About</span>
    <LinkPicker bind:links />
    <label class="check"><input type="checkbox" bind:checked={assign} /> Assign to me</label>
    <div class="actions"><button type="button" class="btn ghost" onclick={onclose}>Cancel</button><button class="btn primary">Post</button></div>
  </form>
</Modal>

<style>
  .form { display: flex; flex-direction: column; gap: 10px; }
  .actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
