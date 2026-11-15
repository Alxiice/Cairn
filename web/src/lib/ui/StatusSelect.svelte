<script lang="ts">
  import { STATUSES, statusLabel, type Status } from '../api'
  // A status pill; with `onchange` it is a menu (a native select, so it works with the keyboard).
  let { status, onchange, suffix = '' }: { status: Status; onchange?: (s: Status) => void; suffix?: string } = $props()
</script>

{#if onchange}
  <select class="pill {status}" value={status} aria-label="Status"
    onclick={(e) => e.stopPropagation()}
    onchange={(e) => onchange((e.currentTarget as HTMLSelectElement).value as Status)}>
    {#each STATUSES as s}<option value={s.id}>{s.label}</option>{/each}
  </select>
{:else}
  <span class="pill {status}">{statusLabel(status)}{#if suffix}<span class="mono v">{suffix}</span>{/if}</span>
{/if}

<style>
  select.pill { appearance: none; cursor: pointer; padding-right: 8px; }
  select.pill option { background: var(--panel); color: var(--fg); }
  .v { opacity: .8; font-weight: 500; }
</style>
