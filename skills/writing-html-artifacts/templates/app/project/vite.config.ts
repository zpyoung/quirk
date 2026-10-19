import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

export default defineConfig({
  base: './',
  plugins: [react(), viteSingleFile()],
  build: {
    modulePreload: { polyfill: false },
    outDir: 'dist',
    assetsInlineLimit: 100_000_000,
  },
})
