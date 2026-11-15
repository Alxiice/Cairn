<script lang="ts">
  // Stroke icons that follow the text color.
  let { name, size = 20 }: { name: string; size?: number } = $props()
  const paths: Record<string, string> = {
    home: 'M4 11 L12 4 L20 11 V20 H4 Z',
    sequences: 'M4 4 H20 V8 H4 Z M4 10 H20 V14 H4 Z M4 16 H20 V20 H4 Z',
    shots: 'M3 6 H21 V18 H3 Z M7 6 V18 M17 6 V18',
    assets: 'M12 3 L20 7.5 V16.5 L12 21 L4 16.5 V7.5 Z M4 7.5 L12 12 L20 7.5 M12 12 V21',
    review: 'M3 5 H21 V19 H3 Z M10 9 L15 12 L10 15 Z',
    notes: 'M4 5 H20 V16 H10 L6 20 V16 H4 Z',
    gear: 'M12 9 A3 3 0 1 0 12.01 9 M12 3 V6 M12 18 V21 M3 12 H6 M18 12 H21 M5.6 5.6 L7.8 7.8 M16.2 16.2 L18.4 18.4 M5.6 18.4 L7.8 16.2 M16.2 7.8 L18.4 5.6',
    search: 'M11 5 A6 6 0 1 0 11.01 5 M16 16 L20 20',
    blender: 'M13 7 A6 6 0 1 0 13.01 7 M13 11 A2 2 0 1 0 13.01 11 M3 9 H11 M6 6 H12',
    folder: 'M3 6 H10 L12 8 H21 V19 H3 Z',
    plus: 'M12 5 V19 M5 12 H19',
    close: 'M6 6 L18 18 M18 6 L6 18',
    link: 'M10 14 L14 10 M8 12 L6 14 A3 3 0 0 0 10 18 L12 16 M16 12 L18 10 A3 3 0 0 0 14 6 L12 8',
    clip: 'M8 12 L14 6 A3 3 0 0 1 18 10 L10 18 A5 5 0 0 1 3 11 L10 4',
    up: 'M12 19 V5 M6 11 L12 5 L18 11',
    play: 'M8 5 L19 12 L8 19 Z',
    open: 'M14 4 H20 V10 M20 4 L11 13 M18 14 V20 H4 V6 H10',
  }
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
  stroke-linejoin="round" stroke-linecap="round" aria-hidden="true"><path d={paths[name] ?? ''} /></svg>
