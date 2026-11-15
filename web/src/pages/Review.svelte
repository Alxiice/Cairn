<script lang="ts">
  import { api, vname, type Entity, type EntityRow, type Note, type Version } from '../lib/api'
  import { act, app, go, route, say } from '../lib/state.svelte'

  // Review: play a version, or compare two (wipe or side by side), step frames, draw on a frame and post a note
  // linked to the shot or asset and both versions. Videos and images play in the browser: mp4, webm, png, jpg.
  const MEDIA = /\.(mp4|webm|mov|m4v|png|jpe?g|webp|gif)$/i
  let entities = $state<EntityRow[]>([])
  let entity = $state<Entity | null>(null)
  let versions = $state<Version[]>([])
  let notes = $state<Note[]>([])
  let a = $state<number | null>(null)
  let b = $state<number | null>(null)
  let urlA = $state('')
  let urlB = $state('')
  let mode = $state<'single' | 'wipe' | 'side'>('single')
  let wipe = $state(50)
  let videoA: HTMLVideoElement | undefined = $state()
  let videoB: HTMLVideoElement | undefined = $state()
  let time = $state(0)
  let duration = $state(0)
  let paused = $state(true)
  let canvas: HTMLCanvasElement | undefined = $state()
  let drawn = $state(false)
  let title = $state('')
  let content = $state('')
  let retake = $state(true)

  const entityId = $derived(Number(route.query.entity) || null)
  const fps = $derived(app.project!.fps)
  const first = $derived(entity?.cut_in ?? 1)
  const frame = $derived(first + Math.floor(time * fps + 1e-6))
  const playable = $derived(versions.filter((v) => v.kind === 'folder' || MEDIA.test(v.path)))
  const VIDEO = /\.(mp4|webm|mov|m4v)$/i

  $effect(() => { api.get<EntityRow[]>(`/projects/${app.project!.id}/entities`).then((e) => (entities = e)) })
  $effect(() => {
    void app.rev
    if (!entityId) return
    api.get<Entity>(`/entities/${entityId}`).then((e) => (entity = e))
    api.get<Version[]>(`/entities/${entityId}/versions`).then((v) => {
      versions = v
      const media = v.filter((x) => x.kind === 'folder' || MEDIA.test(x.path))
      a = Number(route.query.a) || (a && media.some((x) => x.id === a) ? a : media[0]?.id ?? null)
      b = Number(route.query.b) || b
      if (route.query.b) mode = 'wipe'
    })
    api.get<Note[]>(`/projects/${app.project!.id}/notes?target=entity&target_id=${entityId}`).then((n) => (notes = n))
  })

  /** The file to show for a version: itself, or for a folder (render layers) its color layer or first image or video. */
  async function media(id: number | null): Promise<{ url: string; video: boolean }> {
    const v = versions.find((x) => x.id === id)
    if (!v) return { url: '', video: false }
    if (v.kind !== 'folder') return { url: `/api/versions/${v.id}/file`, video: VIDEO.test(v.path) }
    const { files } = await api.get<{ files: string[] }>(`/versions/${v.id}/file`)
    const pick = files.find((f) => /^color\./i.test(f)) ?? files.find((f) => MEDIA.test(f))
    return pick ? { url: `/api/versions/${v.id}/file?name=${encodeURIComponent(pick)}`, video: VIDEO.test(pick) } : { url: '', video: false }
  }
  let videoUrlA = $state(false)
  let videoUrlB = $state(false)
  $effect(() => { media(a).then((m) => { urlA = m.url; videoUrlA = m.video }) })
  $effect(() => { media(b).then((m) => { urlB = m.url; videoUrlB = m.video }) })

  function sync() {
    if (videoA && videoB && Math.abs(videoB.currentTime - videoA.currentTime) > 0.04) videoB.currentTime = videoA.currentTime
  }
  function toggle() {
    if (!videoA) return
    if (videoA.paused) { videoA.play(); videoB?.play() } else { videoA.pause(); videoB?.pause(); sync() }
  }
  function seek(t: number) {
    if (!videoA) return
    videoA.currentTime = Math.max(0, Math.min(t, duration || t))
    if (videoB) videoB.currentTime = videoA.currentTime
  }
  const step = (n: number) => { videoA?.pause(); videoB?.pause(); seek((frame - first + n) / fps + 0.5 / fps) }
  const goFrame = (f: number) => seek((f - first) / fps + 0.5 / fps)

  // drawing on the frame
  let drawing = false
  function down(e: PointerEvent) {
    const ctx = canvas!.getContext('2d')!
    const r = canvas!.getBoundingClientRect()
    ctx.strokeStyle = '#f08080'
    ctx.lineWidth = 4
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(((e.clientX - r.left) / r.width) * canvas!.width, ((e.clientY - r.top) / r.height) * canvas!.height)
    drawing = true
    canvas!.setPointerCapture(e.pointerId)
  }
  function move(e: PointerEvent) {
    if (!drawing) return
    const ctx = canvas!.getContext('2d')!
    const r = canvas!.getBoundingClientRect()
    ctx.lineTo(((e.clientX - r.left) / r.width) * canvas!.width, ((e.clientY - r.top) / r.height) * canvas!.height)
    ctx.stroke()
    drawn = true
  }
  const clear = () => { canvas?.getContext('2d')!.clearRect(0, 0, canvas.width, canvas.height); drawn = false }

  async function post(e: Event) {
    e.preventDefault()
    const links = [{ target: 'entity', id: entity!.id }, ...[a, b].filter(Boolean).map((id) => ({ target: 'version', id }))]
    const n = await act(() => api.post<Note>(`/projects/${app.project!.id}/notes`, { title, content, frame, links, assignees: [1] }))
    if (!n) return
    if (drawn && canvas) {
      const blob = await new Promise<Blob | null>((r) => canvas!.toBlob(r, 'image/png'))
      if (blob) {
        const form = new FormData()
        form.append('file', blob, `frame_${frame}.png`)
        await act(() => api.post(`/notes/${n.id}/attachments`, form))
      }
    }
    if (retake) {
      const v = versions.find((x) => x.id === a)
      const task = entity!.tasks.find((t) => t.id === v?.task_id)
      if (task) await api.patch(`/tasks/${task.id}`, { status: 'ret' })
    }
    say('Note posted')
    title = ''; content = ''; clear()
  }
</script>

<div class="page">
  <div class="toolbar">
    <h1>Review</h1>
    <select class="field" value={entityId ?? ''} onchange={(e) => go(`review?entity=${(e.currentTarget as HTMLSelectElement).value}`)} aria-label="Shot or asset">
      <option value="" disabled>Pick a shot or asset…</option>
      {#each entities as e}<option value={e.id}>{e.kind} · {e.name}</option>{/each}
    </select>
    {#if entity}
      <div class="seg">{#each [['single', 'Single'], ['wipe', 'Compare A | B'], ['side', 'Side by side']] as [k, label]}<button class:on={mode === k} onclick={() => (mode = k as typeof mode)}>{label}</button>{/each}</div>
      <label class="stack inline">A<select class="field" bind:value={a}>{#each playable as v}<option value={v.id}>{vname(v)}</option>{/each}</select></label>
      {#if mode !== 'single'}<label class="stack inline">B<select class="field" bind:value={b}><option value={null}>—</option>{#each playable as v}<option value={v.id}>{vname(v)}</option>{/each}</select></label>{/if}
    {/if}
  </div>

  {#if !entity}
    <p class="empty">Pick a shot or asset. Its videos and images (renders, previz, playblasts) play here.</p>
  {:else if !playable.length}
    <p class="empty">{entity.name} has no video or image version yet. Publish a render or a playblast first.</p>
  {:else}
    <div class="body">
      <main>
        <div class="stage" class:side={mode === 'side'}>
          <div class="view">
            {#if urlA && videoUrlA}
              <video bind:this={videoA} src={urlA} bind:currentTime={time} bind:duration bind:paused ontimeupdate={sync} preload="auto" muted></video>
            {:else if urlA}<img src={urlA} alt="Version A" />{/if}
            {#if mode === 'wipe' && urlB}
              <div class="over" style:clip-path={`inset(0 0 0 ${wipe}%)`}>
                {#if videoUrlB}<video bind:this={videoB} src={urlB} preload="auto" muted></video>{:else}<img src={urlB} alt="Version B" />{/if}
              </div>
              <div class="split" style:left={wipe + '%'}></div>
            {/if}
            <canvas bind:this={canvas} width="1280" height="720" onpointerdown={down} onpointermove={move} onpointerup={() => (drawing = false)} aria-label="Draw on the frame"></canvas>
            <span class="tag corner">A</span>{#if mode === 'wipe' && urlB}<span class="tag corner r">B</span>{/if}
          </div>
          {#if mode === 'side' && urlB}
            <div class="view">{#if videoUrlB}<video bind:this={videoB} src={urlB} preload="auto" muted></video>{:else}<img src={urlB} alt="Version B" />{/if}<span class="tag corner">B</span></div>
          {/if}
        </div>
        {#if mode === 'wipe' && urlB}<input type="range" min="0" max="100" bind:value={wipe} aria-label="Wipe position" />{/if}
        <div class="controls">
          <button class="btn" onclick={() => step(-1)} aria-label="Previous frame">◀◀</button>
          <button class="btn primary" onclick={toggle} aria-label={paused ? 'Play' : 'Pause'}>{paused ? '▶' : '❚❚'}</button>
          <button class="btn" onclick={() => step(1)} aria-label="Next frame">▶▶</button>
          <span class="mono">frame {frame}</span><span class="muted">· {fps} fps</span>
          {#if drawn}<button class="btn ghost small" onclick={clear}>Clear drawing</button>{/if}
        </div>
        <div class="timeline">
          <input type="range" min="0" max={duration || 1} step={1 / fps} value={time} oninput={(e) => seek(Number((e.currentTarget as HTMLInputElement).value))} aria-label="Timeline" />
          {#each notes.filter((n) => n.frame !== null && duration && n.frame >= first && (n.frame - first) / fps <= duration) as n}
            <button class="mark" style:left={`${(((n.frame! - first) / fps) / duration) * 100}%`} title={n.title} onclick={() => goFrame(n.frame!)} aria-label={`Note on frame ${n.frame}: ${n.title}`}></button>
          {/each}
        </div>
        <span class="muted small">Draw on the picture, then write the note: it is linked to {entity.name}, version A{mode !== 'single' && b ? ' and B' : ''}, at frame {frame}. Red marks: frames with notes.</span>
      </main>
      <aside class="panel side">
        <form class="form" onsubmit={post}>
          <span class="label">Note on frame {frame}</span>
          <input class="field" bind:value={title} placeholder="Title" required />
          <textarea class="field" rows="4" bind:value={content} placeholder="What to change"></textarea>
          <label class="check"><input type="checkbox" bind:checked={retake} /> Set the task of A to Retake</label>
          <button class="btn primary">Post note</button>
        </form>
        <span class="label">On this {entity.kind}</span>
        {#each notes as n (n.id)}
          <div class="old">
            {#if n.frame !== null}<button class="btn ghost small mono" onclick={() => goFrame(n.frame!)}>f {n.frame}</button>{/if}
            <a href={`#/notes/${n.id}`}>{n.title}</a><span class="pill {n.status === 'open' ? 'wip' : 'app'}">{n.status}</span>
          </div>
        {:else}<span class="muted small">No note yet.</span>{/each}
      </aside>
    </div>
  {/if}
</div>

<style>
  .page { padding: 14px 18px; display: flex; flex-direction: column; gap: 12px; }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
  h1 { font-size: 20px; }
  .inline { flex-direction: row; align-items: center; }
  .seg { display: inline-flex; border: 1px solid var(--line-2); border-radius: 7px; overflow: hidden; }
  .seg button { padding: 6px 11px; background: none; border: 0; color: var(--muted); font-weight: 600; font-size: 12px; cursor: pointer; }
  .seg button.on { background: var(--select); color: var(--fg); }
  .body { display: flex; flex-wrap: wrap; gap: 14px; }
  main { flex: 999 1 640px; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
  .stage { display: grid; gap: 8px; }
  .stage.side { grid-template-columns: 1fr 1fr; }
  .view { position: relative; aspect-ratio: 16 / 9; background: #000; border-radius: 10px; overflow: hidden; }
  .view video, .view img, .over video, .over img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }
  .over { position: absolute; inset: 0; }
  .split { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--accent); }
  canvas { position: absolute; inset: 0; width: 100%; height: 100%; cursor: crosshair; touch-action: none; }
  .corner { position: absolute; left: 10px; top: 10px; }
  .corner.r { left: auto; right: 10px; }
  .controls { display: flex; align-items: center; gap: 10px; }
  .timeline { position: relative; overflow: hidden; padding-top: 6px; }
  .timeline input { width: 100%; }
  .mark { position: absolute; top: 0; width: 10px; height: 10px; border-radius: 50%; background: var(--bad); border: 0; transform: translateX(-5px); cursor: pointer; padding: 0; }
  .side { flex: 1 1 300px; padding: 14px; display: flex; flex-direction: column; gap: 10px; align-self: flex-start; }
  .form { display: flex; flex-direction: column; gap: 8px; }
  .old { display: flex; align-items: center; gap: 8px; font-size: 13px; }
</style>
