<script lang="ts">
  import { api, vname, type EntityRow, type LinkRef, type VersionPick } from '../api'
  import { app } from '../state.svelte'

  // What a note is about: shots, assets, their versions and their tasks. Chips with a remove button, and a picker.
  let { links = $bindable([]) }: { links: LinkRef[] } = $props()

  let entities = $state<EntityRow[]>([])
  let versions = $state<VersionPick[]>([])
  let pick = $state('')

  $effect(() => {
    const pid = app.project!.id
    api.get<EntityRow[]>(`/projects/${pid}/entities`).then((e) => (entities = e))
    api.get<VersionPick[]>(`/projects/${pid}/versions`).then((v) => (versions = v))
  })

  const options = $derived([
    ...entities.map((e) => ({ key: `entity:${e.id}`, group: e.kind === 'shot' ? 'Shots' : 'Assets', label: e.name })),
    ...versions.map((v) => ({ key: `version:${v.id}`, group: 'Versions', label: `${v.entity} · ${vname(v)}` })),
    ...entities.flatMap((e) => e.tasks.filter((t) => t.enabled).map((t) => ({ key: `task:${t.id}`, group: 'Tasks', label: `${e.name} · ${t.name}` }))),
  ])
  const groups = ['Shots', 'Assets', 'Versions', 'Tasks']
  const label = (l: LinkRef) => l.label ?? options.find((o) => o.key === `${l.target}:${l.id}`)?.label ?? `${l.target} ${l.id}`

  function add() {
    if (!pick) return
    const [target, id] = pick.split(':')
    if (!links.some((l) => l.target === target && l.id === Number(id)))
      links = [...links, { target: target as LinkRef['target'], id: Number(id), label: options.find((o) => o.key === pick)?.label }]
    pick = ''
  }
</script>

<div class="links">
  {#each links as l (l.target + l.id)}
    <span class="tag">{label(l)}<button type="button" class="x" aria-label={`Unlink ${label(l)}`}
      onclick={() => (links = links.filter((x) => x !== l))}>✕</button></span>
  {/each}
  <select class="field" bind:value={pick} onchange={add} aria-label="Link a shot, asset, version or task">
    <option value="">+ Link a shot, asset, version or task…</option>
    {#each groups as g}
      <optgroup label={g}>{#each options.filter((o) => o.group === g) as o}<option value={o.key}>{o.label}</option>{/each}</optgroup>
    {/each}
  </select>
</div>

<style>
  .links { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .x { background: none; border: 0; color: var(--muted); cursor: pointer; padding: 0 0 0 4px; font-size: 10px; }
  .x:hover { color: var(--bad); }
  select { flex: 1 1 220px; }
</style>
