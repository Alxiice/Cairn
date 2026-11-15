<script lang="ts">
  import { api, type Hit } from './lib/api'
  import { app, go, listen, loadPlugins, loadProjects, pickProject, route } from './lib/state.svelte'
  import Icon from './lib/ui/Icon.svelte'
  import NewEntity from './lib/ui/NewEntity.svelte'
  import NoteDialog from './lib/ui/NoteDialog.svelte'
  import Assets from './pages/Assets.svelte'
  import Entity from './pages/Entity.svelte'
  import Home from './pages/Home.svelte'
  import Notes from './pages/Notes.svelte'
  import PluginPage from './pages/PluginPage.svelte'
  import Review from './pages/Review.svelte'
  import Sequences from './pages/Sequences.svelte'
  import Settings from './pages/Settings.svelte'
  import Shots from './pages/Shots.svelte'
  import Welcome from './pages/Welcome.svelte'

  const spaces = [
    { id: 'home', label: 'Home', icon: 'home' }, { id: 'sequences', label: 'Sequences', icon: 'sequences' },
    { id: 'shots', label: 'Shots', icon: 'shots' },
    { id: 'assets', label: 'Assets', icon: 'assets' }, { id: 'review', label: 'Review', icon: 'review' },
    { id: 'notes', label: 'Notes', icon: 'notes' },
  ]
  let ready = $state(false)
  let error = $state('')
  let menu = $state(false)
  let newMenu = $state(false)
  let creating = $state<'shot' | 'asset' | 'note' | null>(null)
  let query = $state('')
  let hits = $state<Hit[]>([])
  let hitIndex = $state(0)
  let searchBox: HTMLInputElement | undefined = $state()

  $effect(() => {
    Promise.all([loadProjects(), loadPlugins()])
      .then(() => (ready = true))
      .catch((e) => (error = String(e)))
    listen()
  })

  let searchTimer = 0
  function search() {
    clearTimeout(searchTimer)
    searchTimer = window.setTimeout(async () => {
      hits = query.trim() && app.project ? await api.get<Hit[]>(`/projects/${app.project.id}/search?q=${encodeURIComponent(query)}`) : []
      hitIndex = 0
    }, 120)
  }
  function openHit(h: Hit) {
    query = ''
    hits = []
    if (h.type === 'note') go(`notes/${h.id}`)
    else if (h.type === 'version') go(`entity/${h.entity_id}`)
    else go(`entity/${h.id}`)
  }
  function searchKeys(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') { hitIndex = Math.min(hitIndex + 1, hits.length - 1); e.preventDefault() }
    else if (e.key === 'ArrowUp') { hitIndex = Math.max(hitIndex - 1, 0); e.preventDefault() }
    else if (e.key === 'Enter' && hits[hitIndex]) openHit(hits[hitIndex])
    else if (e.key === 'Escape') { query = ''; hits = [] }
  }
  function globalKeys(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); searchBox?.focus() }
  }
  const active = $derived(route.parts[0] === 'entity' ? '' : route.parts[0] === 'plugin' ? 'plugin/' + route.parts[1] : route.parts[0])
</script>

<svelte:window onkeydown={globalKeys} />

{#if error}
  <div class="empty">The server does not answer: {error}</div>
{:else if ready && !app.project}
  <Welcome />
{:else if ready}
  <div class="shell">
    <nav class="rail" aria-label="Workspaces">
      <a class="logo" href="#/home" aria-label="Cairn home"><img src="/logo.svg" alt="" width="34" height="34" /></a>
      {#each spaces as s}
        <a href={`#/${s.id}`} class:on={active === s.id} title={s.label}><Icon name={s.icon} /><span>{s.label}</span></a>
      {/each}
      {#if app.plugins.some((p) => p.ui && !p.error)}<div class="sep"></div>{/if}
      {#each app.plugins.filter((p) => p.ui && !p.error) as p}
        <a href={`#/plugin/${p.id}`} class:on={active === 'plugin/' + p.id} title={p.description || p.name}>
          <span class="picon">{@html p.icon}</span><span>{p.name}</span>
        </a>
      {/each}
      <a href="#/settings" class="bottom" class:on={active === 'settings'} title="Project settings"><Icon name="gear" /><span>Settings</span></a>
    </nav>
    <div class="main">
      <header>
        <div class="proj">
          <button class="field projbtn" onclick={() => (menu = !menu)} aria-expanded={menu}><b>{app.project!.name}</b><span class="muted">▾</span></button>
          {#if menu}
            <div class="menu panel">
              {#each app.projects as p}<button class="item" class:cur={p.id === app.project!.id} onclick={() => { menu = false; pickProject(p) }}>{p.name}<span class="muted mono small">{p.code}</span></button>{/each}
              <button class="item" onclick={() => { menu = false; go('new-project') }}>+ New project…</button>
            </div>
          {/if}
        </div>
        <div class="search">
          <Icon name="search" size={16} />
          <input bind:this={searchBox} bind:value={query} oninput={search} onkeydown={searchKeys} placeholder="Search shots, assets, versions, notes…" aria-label="Search" />
          <span class="kbd">Ctrl K</span>
          {#if hits.length}
            <div class="hits panel" role="listbox">
              {#each hits as h, i}
                <button class="item" class:cur={i === hitIndex} role="option" aria-selected={i === hitIndex} onclick={() => openHit(h)}>
                  <span class="label kind">{h.type}</span><span class="grow">{h.label}</span><span class="muted small">{h.detail}</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
        <span class="pill" class:app={app.connected} class:ret={!app.connected}>{app.connected ? '● Live' : '○ Offline'}</span>
        <div class="proj">
          <button class="btn primary" onclick={() => (newMenu = !newMenu)} aria-expanded={newMenu}><Icon name="plus" size={16} />New</button>
          {#if newMenu}
            <div class="menu panel right">
              <button class="item" onclick={() => { newMenu = false; creating = 'shot' }}>Shot</button>
              <button class="item" onclick={() => { newMenu = false; creating = 'asset' }}>Asset</button>
              <button class="item" onclick={() => { newMenu = false; creating = 'note' }}>Note</button>
            </div>
          {/if}
        </div>
      </header>
      <main>
        {#key app.project!.id}
          {#if route.parts[0] === 'home'}<Home />
          {:else if route.parts[0] === 'sequences'}<Sequences />
          {:else if route.parts[0] === 'shots'}<Shots />
          {:else if route.parts[0] === 'assets'}<Assets />
          {:else if route.parts[0] === 'entity'}{#key route.parts[1]}<Entity id={Number(route.parts[1])} />{/key}
          {:else if route.parts[0] === 'review'}<Review />
          {:else if route.parts[0] === 'notes'}<Notes />
          {:else if route.parts[0] === 'settings'}<Settings />
          {:else if route.parts[0] === 'new-project'}<Welcome />
          {:else if route.parts[0] === 'plugin'}{#key route.parts[1]}<PluginPage id={route.parts[1]} />{/key}
          {:else}<Home />{/if}
        {/key}
      </main>
    </div>
  </div>
{/if}

{#if creating === 'shot' || creating === 'asset'}<NewEntity kind={creating} onclose={() => (creating = null)} />{/if}
{#if creating === 'note'}<NoteDialog onclose={() => (creating = null)} />{/if}
{#if app.toast}<div class="toast" class:error={app.toast.error} role="status">{app.toast.text}</div>{/if}

<style>
  .shell { display: flex; height: 100vh; }
  .rail { flex: 0 0 68px; background: var(--bg-deep); border-right: 1px solid var(--line-soft); display: flex; flex-direction: column; gap: 3px; padding: 10px 6px; overflow-y: auto; }
  .rail a { display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 8px 0; color: var(--muted); text-decoration: none; font: 600 10px var(--sans); border-radius: 8px; }
  .rail a:hover { color: var(--fg); background: var(--hover-soft); }
  .rail a.on { color: var(--accent-text); background: var(--raised); }
  .rail .logo { padding: 2px 0 12px; }
  .rail .logo:hover { background: none; }
  .rail .bottom { margin-top: auto; }
  .sep { height: 1px; background: var(--line); margin: 6px 8px; }
  .picon { display: flex; width: 20px; height: 20px; }
  .picon :global(svg) { width: 20px; height: 20px; }
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  header { display: flex; align-items: center; gap: 12px; padding: 10px 18px; border-bottom: 1px solid var(--line-soft); background: var(--bar); flex-wrap: wrap; }
  .proj { position: relative; }
  .projbtn { display: flex; gap: 8px; align-items: center; cursor: pointer; background: transparent; }
  .menu { position: absolute; top: 38px; left: 0; min-width: 240px; padding: 6px; z-index: 40; display: flex; flex-direction: column; background: var(--panel-2); }
  .menu.right { left: auto; right: 0; min-width: 160px; }
  .item { display: flex; gap: 10px; align-items: center; justify-content: space-between; padding: 8px 10px; border: 0; border-radius: 6px; background: none; color: var(--fg); text-align: left; cursor: pointer; }
  .item:hover, .item.cur { background: var(--select); }
  .search { position: relative; margin-left: auto; flex: 0 1 440px; display: flex; align-items: center; gap: 8px; background: var(--panel-2); border: 1px solid var(--line-2); border-radius: 7px; padding: 0 10px; color: var(--muted); }
  .search input { flex: 1; min-width: 0; background: none; border: 0; outline: none; padding: 7px 0; color: var(--fg); }
  .hits { position: absolute; top: 38px; left: 0; right: 0; padding: 6px; z-index: 40; background: var(--panel-2); }
  .kind { width: 64px; }
  .grow { flex: 1; }
  main { flex: 1; min-height: 0; overflow: auto; }
  .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--raised); border: 1px solid var(--line-2); border-radius: 9px; padding: 10px 16px; z-index: 60; max-width: 80vw; }
  .toast.error { border-color: var(--bad); background: var(--bad-bg); }
</style>
