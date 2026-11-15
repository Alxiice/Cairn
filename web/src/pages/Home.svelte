<script lang="ts">
  import { ago, api, vnum, type Activity, type EntityRow, type Sequence, type Status } from '../lib/api'
  import { openInBlender } from '../lib/actions'
  import { app, go } from '../lib/state.svelte'
  import StatusSelect from '../lib/ui/StatusSelect.svelte'
  import Thumb from '../lib/ui/Thumb.svelte'

  interface MyTask { id: number; name: string; status: Status; entity_id: number; entity: string; kind: string; latest: number | null }
  let tasks = $state<MyTask[]>([])
  let activity = $state<Activity[]>([])
  let entities = $state<EntityRow[]>([])
  let sequences = $state<Sequence[]>([])

  $effect(() => {
    void app.rev
    const pid = app.project!.id
    api.get<MyTask[]>(`/projects/${pid}/my-tasks`).then((t) => (tasks = t))
    api.get<Activity[]>(`/projects/${pid}/activity`).then((a) => (activity = a))
    api.get<EntityRow[]>(`/projects/${pid}/entities`).then((e) => (entities = e))
    api.get<Sequence[]>(`/projects/${pid}/sequences`).then((s) => (sequences = s))
  })

  const progress = $derived(sequences.map((s) => {
    const all = entities.filter((e) => e.sequence_id === s.id).flatMap((e) => e.tasks.filter((t) => t.enabled))
    const pct = (st: string[]) => (all.length ? Math.round((100 * all.filter((t) => st.includes(t.status)).length) / all.length) : 0)
    return { name: s.name, shots: s.shot_count, done: pct(['app', 'skip']), review: pct(['rev']) }
  }))
  const recent = $derived([...entities].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 6))
  const dot: Record<string, string> = { published: 'var(--teal)', noted: 'var(--bad)', set: 'var(--ok)', created: 'var(--accent)' }

  async function latestOf(t: MyTask) {
    const versions = await api.get<{ id: number; task_id: number }[]>(`/entities/${t.entity_id}/versions`)
    const v = versions.find((x) => x.task_id === t.id)
    if (v) openInBlender(v.id)
  }
</script>

<div class="page">
  <div class="title"><h1>Home</h1><span class="muted">{tasks.length} tasks in progress · {app.project!.name}</span></div>
  <div class="row">
    <section class="panel box wide">
      <b>My tasks</b>
      {#if tasks.length}
        <table class="grid">
          <thead><tr><th>Shot or asset</th><th>Task</th><th>Status</th><th>Latest</th><th></th></tr></thead>
          <tbody>
            {#each tasks as t (t.id)}
              <tr class="row" onclick={() => go(`entity/${t.entity_id}`)}>
                <td><b>{t.entity}</b> <span class="muted small">{t.kind}</span></td><td>{t.name}</td>
                <td><StatusSelect status={t.status} onchange={(s) => api.patch(`/tasks/${t.id}`, { status: s })} /></td>
                <td class="mono small">{vnum(t.latest)}</td>
                <td>{#if t.latest}<button class="btn ghost small" onclick={(e) => { e.stopPropagation(); latestOf(t) }} aria-label={`Open ${t.entity} ${t.name} in Blender`}>Open</button>{/if}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {:else}<p class="empty">Nothing in progress. Tasks you set to WIP, Review or Retake show up here.</p>{/if}
    </section>
    <section class="panel box">
      <b>Activity</b>
      {#each activity.slice(0, 14) as a (a.id)}
        <div class="act"><span class="dot" style:background={dot[a.verb] ?? 'var(--muted)'}></span><span><span class="muted">{a.verb}</span> {a.label}</span><span class="muted small when">{ago(a.at)}</span></div>
      {:else}<p class="muted">No activity yet.</p>{/each}
    </section>
  </div>
  <div class="row">
    <section class="panel box">
      <b>Progress by sequence</b>
      {#each progress as s}
        <div class="seq"><span class="sname">{s.name}</span><div class="bar grow"><div style:width={s.done + '%'} style:background="var(--ok)"></div><div style:width={s.review + '%'} style:background="var(--teal)"></div></div><span class="mono muted small">{s.shots} shots</span></div>
      {:else}<p class="muted">No sequence yet: add them in Settings.</p>{/each}
      <span class="muted small"><span style:color="var(--ok)">■</span> approved or skipped <span style:color="var(--teal)">■</span> in review</span>
    </section>
    <section class="panel box wide">
      <b>Recently updated</b>
      <div class="recent">
        {#each recent as e (e.id)}
          <a href={`#/entity/${e.id}`} class="rcard"><Thumb item={e} width="150px" height="84px" /><b>{e.name}</b><span class="muted small">{e.kind} · {ago(e.updated_at)}</span></a>
        {:else}<p class="muted">Create a shot or an asset with “New”.</p>{/each}
      </div>
    </section>
  </div>
</div>

<style>
  .page { padding: 18px; display: flex; flex-direction: column; gap: 14px; }
  .title { display: flex; align-items: baseline; gap: 12px; }
  h1 { font-size: 26px; }
  .row { display: flex; flex-wrap: wrap; gap: 14px; }
  .box { flex: 1 1 340px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .wide { flex: 2 1 560px; }
  .act { display: flex; gap: 10px; align-items: baseline; font-size: 13px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 8px; }
  .when { margin-left: auto; white-space: nowrap; }
  .seq { display: flex; align-items: center; gap: 10px; }
  .sname { width: 80px; }
  .grow { flex: 1; }
  .recent { display: flex; flex-wrap: wrap; gap: 12px; }
  .rcard { display: flex; flex-direction: column; gap: 4px; width: 150px; color: var(--fg); text-decoration: none; }
  p { margin: 0; }
</style>
