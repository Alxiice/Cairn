import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// `npm run dev` serves the UI on 5173 and forwards the API to a server started with `py -m cairn serve`.
export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true },
      '/plugins': { target: 'http://127.0.0.1:8765', changeOrigin: true },
    },
  },
})
