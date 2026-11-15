<script lang="ts">
  import { ago, api, vnum, type Entity, type Note } from '../api'
  import { app, deleteEntity, go } from '../state.svelte'
  import StatusSelect from './StatusSelect.svelte'
  import Thumb from './Thumb.svelte'

  // The side panel of the Shots table and the Assets library: what the selected item is, its pipeline, its latest note.
  let { id, onclose }: { id: number; onclose: () => void } = $props()
  let e = $state<Entity | null>(null)
  let notes = $state<Note[]>([])

  $effect(() => {
    void app.rev
    api.get<Entity>(`/entities/${id}`).then((x) => (e = x))
    api.get<Note[]>(`/projects/${app.project!.id}/notes?target=entity&target_id=${id}`).then((n) => (notes = n))
  })
</script>

<aside class="panel drawer">
  {#if e}
    <div class="head">
      <h2>{e.name}</h2><span class="tag">{e.kind === 'shot' ? e.sequence ?? 'no sequence' : e.asset_type}</span>
      <a class="btn ghost small" href={`#/entity/${e.id}`}>Open ↗</a>
      <button class="btn ghost small" onclick={onclose} aria-label="Close the panel">✕</button>
    </div>
    {#if e.title}<span class="soft">{e.title}</span>{/if}
    <Thumb item={e} width="100%" height="160px" />
    <div class="facts">
      {#if e.kind === 'shot'}<span class="muted">Frames</span><span class="mono small">head {e.head}–{e.tail} · cut {e.cut_in}–{e.cut_out}</span>{/if}
      <span class="muted">{e.kind === 'shot' ? 'Assets' : 'Uses'}</span>
      <span class="tags">{#each e.uses as u}<a class="tag" href={`#/entity/${u.id}`}>{u.name}</a>{:else}<span class="muted">—</span>{/each}</span>
      {#if e.kind === 'asset'}
        <span class="muted">Used in</span>
        <span class="tags">{#each e.used_in as u}<a class="tag" href={`#/entity/${u.id}`}>{u.name}</a>{:else}<span class="muted">—</span>{/each}</span>
      {/if}
    </div>
    <span class="label">Pipeline</span>
    {#each e.tasks.filter((t) => t.enabled) as t (t.id)}
      <div class="task"><span class="tname">{t.name}</span>
        <StatusSelect status={t.status} onchange={(s) => api.patch(`/tasks/${t.id}`, { status: s })} />
        <span class="mono muted small v">{vnum(t.latest)}</span></div>
    {:else}<span class="muted">No task</span>{/each}
    <span class="label">Latest note</span>
    {#if notes[0]}
      <a class="note" href={`#/notes/${notes[0].id}`}><b>{notes[0].title}</b><span class="soft small">{notes[0].content.slice(0, 140)}</span><span class="muted small">{ago(notes[0].updated_at)} · {notes[0].status}</span></a>
    {:else}<span class="muted small">No note</span>{/if}
    <div class="actions"><button class="btn primary" onclick={() => go(`entity/${e!.id}`)}>Open page</button><a class="btn" href={`#/review?entity=${e.id}`}>Review</a>
      <button class="btn ghost danger end" onclick={async () => (await deleteEntity({ ...e!, version_count: e!.tasks.reduce((n, t) => n + t.version_count, 0) })) && onclose()}>Delete</button></div>
  {/if}
</aside>

<style>
  .drawer { flex: 0 0 330px; margin: 0 14px 14px 0; padding: 14px; display: flex; flex-direction: column; gap: 10px; align-self: flex-start; position: sticky; top: 0; }
  .head { display: flex; align-items: center; gap: 8px; }
  h2 { font-size: 20px; margin-right: auto; }
  .facts { display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; font-size: 13px; }
  .tags { display: flex; flex-wrap: wrap; gap: 4px; }
  .task { display: flex; align-items: center; gap: 8px; }
  .tname { width: 96px; }
  .v { margin-left: auto; }
  .note { display: flex; flex-direction: column; gap: 3px; background: var(--panel-2); border-radius: 8px; padding: 10px; color: var(--fg); text-decoration: none; }
  .actions { display: flex; gap: 8px; margin-top: 4px; }
  .end { margin-left: auto; }
</style>
