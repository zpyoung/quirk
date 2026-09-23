import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

export default defineConfig({
  base: './',
  plugins: [react(), viteSingleFile()],
  build: {
    modulePreload: { polyfill: false },
    outDir: '..',
    emptyOutDir: false,
    assetsInlineLimit: 100_000_000,
    rollupOptions: { input: 'review-template.html' },
  },
})
