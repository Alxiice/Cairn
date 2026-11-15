<script lang="ts">
  import { app } from '../lib/state.svelte'

  // A plugin's workspace: its own page (served by the server under /plugins/<id>/), told which project is open.
  let { id }: { id: string } = $props()
  const plugin = $derived(app.plugins.find((p) => p.id === id))
</script>

{#if plugin?.ui}
  <iframe src={`${plugin.ui}?project=${app.project!.id}`} title={plugin.name}></iframe>
{:else}
  <p class="empty">No plugin {id}.</p>
{/if}

<style>
  iframe { width: 100%; height: 100%; border: 0; display: block; background: var(--bg); }
</style>
