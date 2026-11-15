<script lang="ts">
  import type { Snippet } from 'svelte'
  // A dialog over the page. Esc or the backdrop closes it.
  let { title, onclose, children, width = '520px' }: { title: string; onclose: () => void; children: Snippet; width?: string } = $props()
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onclose()} />
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="back" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="dlg panel" role="dialog" aria-modal="true" aria-label={title} style:width>
    <div class="head"><h2>{title}</h2><button class="btn ghost small" onclick={onclose} aria-label="Close">✕</button></div>
    {@render children()}
  </div>
</div>

<style>
  .back { position: fixed; inset: 0; background: var(--shade); display: flex; align-items: flex-start; justify-content: center; padding-top: 10vh; z-index: 50; }
  .dlg { max-width: calc(100% - 32px); max-height: 80vh; overflow: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; background: var(--panel); box-shadow: 0 24px 70px var(--shadow); }
  .head { display: flex; align-items: center; justify-content: space-between; }
  h2 { font-size: 18px; }
</style>
