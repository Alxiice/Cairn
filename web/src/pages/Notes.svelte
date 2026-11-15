<script lang="ts">
  import { ago, api, type Attachment, type LinkRef, type Note } from '../lib/api'
  import { act, app, go, route } from '../lib/state.svelte'
  import LinkPicker from '../lib/ui/LinkPicker.svelte'
  import NoteDialog from '../lib/ui/NoteDialog.svelte'

  // Notes inbox: filters, the list, and the selected thread with its links (shots, assets, versions, tasks),
  // attachments and replies.
  let list = $state<Note[]>([])
  let note = $state<Note | null>(null)
  let filter = $state<'open' | 'mine' | 'closed' | 'all'>('open')
  let reply = $state('')
  let replyFile = $state<FileList | null>(null)
  let links = $state<LinkRef[]>([])
  let editingLinks = $state(false)
  let creating = $state(false)
  const selected = $derived(Number(route.parts[1]) || null)

  $effect(() => {
    void app.rev
    api.get<Note[]>(`/projects/${app.project!.id}/notes${filter === 'open' || filter === 'mine' ? '?status=open' : filter === 'closed' ? '?status=closed' : ''}`)
      .then((n) => (list = filter === 'mine' ? n.filter((x) => x.assignees?.includes(1)) : n))
  })
  $effect(() => {
    void app.rev
    if (selected) api.get<Note>(`/notes/${selected}`).then((n) => { note = n; if (!editingLinks) links = n.links })
    else note = null
  })

  const isImage = (a: Attachment) => /\.(png|jpe?g|webp|gif)$/i.test(a.name)
  async function sendReply(e: Event) {
    e.preventDefault()
    if (reply.trim()) await act(() => api.post(`/notes/${note!.id}/replies`, { content: reply }))
    if (replyFile?.[0]) {
      const form = new FormData()
      form.append('file', replyFile[0])
      await act(() => api.post(`/notes/${note!.id}/attachments`, form))
    }
    reply = ''
    replyFile = null
  }
  async function saveLinks() {
    if (await act(() => api.patch(`/notes/${note!.id}`, { links: links.map(({ target, id }) => ({ target, id })) }), 'Links saved'))
      editingLinks = false
  }
  const linkHref = (l: LinkRef) => (l.target === 'version' ? `#/review?entity=${l.entity_id}&a=${l.id}` : `#/entity/${l.entity_id}`)
</script>

<div class="layout">
  <aside class="filters">
    {#each [['open', 'Open'], ['mine', 'Assigned to me'], ['closed', 'Closed'], ['all', 'All']] as [k, label]}
      <button class:on={filter === k} onclick={() => (filter = k as typeof filter)}>{label}</button>
    {/each}
    <button class="btn primary new" onclick={() => (creating = true)}>+ Note</button>
  </aside>
  <div class="panel list">
    {#each list as n (n.id)}
      <a class="item" class:sel={n.id === selected} href={`#/notes/${n.id}`}>
        <span class="line"><b class="grow">{n.title}</b><span class="muted small">{ago(n.updated_at)}</span></span>
        <span class="line">{#each n.links.slice(0, 3) as l}<span class="tag">{l.label}</span>{/each}
          <span class="pill {n.status === 'open' ? 'wip' : 'app'}">{n.status}</span><span class="muted small right">{n.reply_count} repl{n.reply_count === 1 ? 'y' : 'ies'}</span></span>
      </a>
    {:else}<p class="empty">No note here.</p>{/each}
  </div>
  <main class="panel thread">
    {#if note}
      <div class="line"><h1 class="grow">{note.title}</h1>
        <button class="btn" onclick={() => act(() => api.patch(`/notes/${note!.id}`, { status: note!.status === 'open' ? 'closed' : 'open' }))}>{note.status === 'open' ? 'Close' : 'Reopen'}</button></div>
      <div class="line">
        {#if editingLinks}
          <LinkPicker bind:links />
          <button class="btn primary small" onclick={saveLinks}>Save links</button><button class="btn ghost small" onclick={() => { editingLinks = false; links = note!.links }}>Cancel</button>
        {:else}
          {#each note.links as l}<a class="tag" href={linkHref(l)}>{l.target === 'version' ? '▶ ' : ''}{l.label}</a>{/each}
          {#if note.frame !== null}<span class="tag">frame {note.frame}</span>{/if}
          <button class="btn ghost small" onclick={() => (editingLinks = true)}>Edit links</button>
        {/if}
      </div>
      <p class="soft content">{note.content}</p>
      <div class="atts">{#each note.attachments ?? [] as a}
        {#if a.kind === 'url'}<a class="tag" href={a.value} target="_blank" rel="noreferrer">🔗 {a.name}</a>
        {:else if isImage(a)}<a href={`/api/attachments/${a.id}`} target="_blank"><img src={`/api/attachments/${a.id}`} alt={a.name} /></a>
        {:else}<a class="tag" href={`/api/attachments/${a.id}`}>📎 {a.name}</a>{/if}
      {/each}</div>
      <div class="replies">
        {#each note.replies ?? [] as r (r.id)}
          <div class="reply"><span class="muted small">You · {ago(r.created_at)}</span><span class="soft">{r.content}</span></div>
        {/each}
      </div>
      <form class="replybox" onsubmit={sendReply}>
        <textarea class="field" rows="3" bind:value={reply} placeholder="Reply…"></textarea>
        <div class="line"><input type="file" bind:files={replyFile} aria-label="Attach a file" /><button class="btn primary right">Send</button></div>
      </form>
      <span class="muted small">Created {ago(note.created_at)}{#if note.updated_at !== note.created_at} · updated {ago(note.updated_at)}{/if}</span>
    {:else}
      <p class="empty">Select a note. Notes link shots, assets, their versions and tasks; open a version link to review it.</p>
    {/if}
  </main>
</div>
{#if creating}<NoteDialog onclose={() => (creating = false)} />{/if}
<svelte:window onkeydown={(e) => e.key === 'Escape' && selected && !creating && go('notes')} />

<style>
  .layout { display: flex; flex-wrap: wrap; gap: 14px; padding: 14px 18px; min-height: 100%; align-items: flex-start; }
  .filters { flex: 0 0 170px; display: flex; flex-direction: column; gap: 4px; }
  .filters button:not(.btn) { text-align: left; padding: 7px 10px; border-radius: 7px; border: 0; background: none; color: var(--soft); cursor: pointer; }
  .filters button.on { background: var(--hover); color: var(--fg); }
  .new { margin-top: 10px; }
  .list { flex: 1 1 340px; padding: 6px; display: flex; flex-direction: column; gap: 2px; max-height: calc(100vh - 110px); overflow: auto; }
  .item { display: flex; flex-direction: column; gap: 5px; padding: 10px 12px; border-radius: 8px; border: 1px solid transparent; color: var(--fg); text-decoration: none; }
  .item:hover { background: var(--hover-soft); }
  .item.sel { background: var(--hover); border-color: var(--accent); }
  .line { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .grow { flex: 1; }
  .right { margin-left: auto; }
  .thread { flex: 999 1 520px; min-width: 0; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
  h1 { font-size: 20px; }
  .content { white-space: pre-wrap; margin: 0; }
  .atts { display: flex; flex-wrap: wrap; gap: 8px; }
  .atts img { max-width: 320px; max-height: 180px; border-radius: 8px; display: block; }
  .replies { border-left: 2px solid var(--line); padding-left: 12px; display: flex; flex-direction: column; gap: 10px; }
  .reply { display: flex; flex-direction: column; gap: 2px; white-space: pre-wrap; }
  .replybox { display: flex; flex-direction: column; gap: 6px; }
</style>
