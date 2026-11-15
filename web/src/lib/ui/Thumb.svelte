<script lang="ts">
  import { thumbUrl } from '../api'
  // A shot or asset thumbnail, or a colored placeholder made from its name.
  let { item, width = '64px', height = '36px' }: { item: { id: number; name: string; thumbnail: string }; width?: string; height?: string } = $props()
  const hue = $derived([...item.name].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7))
</script>

<div class="thumb" style:width style:height style:background={`linear-gradient(135deg, hsl(${hue} 30% 18%), hsl(${(hue + 40) % 360} 35% 12%))`}>
  {#if item.thumbnail}<img src={thumbUrl(item)} alt="" loading="lazy" />{:else}<span>{item.name.slice(0, 2).toUpperCase()}</span>{/if}
</div>

<style>
  .thumb { position: relative; border-radius: 5px; overflow: hidden; flex: 0 0 auto; display: flex; align-items: center; justify-content: center; }
  img { width: 100%; height: 100%; object-fit: cover; display: block; }
  span { font: 700 11px var(--mono); color: rgba(255, 255, 255, .35); }
</style>
