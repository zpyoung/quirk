import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'vite'

const appRoot = fileURLToPath(new URL('../', import.meta.url))
const configPath = resolve(appRoot, 'vite.config.ts')
const committedTemplatePath = resolve(appRoot, '../review-template.html')

const tempOutDir = await mkdtemp(join(tmpdir(), 'quirk-template-check-'))

try {
  await build({
    root: appRoot,
    configFile: configPath,
    logLevel: 'silent',
    build: {
      outDir: tempOutDir,
      emptyOutDir: true,
    },
  })

  const [built, committed] = await Promise.all([
    readFile(resolve(tempOutDir, 'review-template.html')),
    readFile(committedTemplatePath),
  ])

  if (!built.equals(committed)) {
    console.error('review-template.html is stale; run pnpm run build')
    process.exit(1)
  }

  console.log('review-template.html matches a fresh build.')
} finally {
  await rm(tempOutDir, { recursive: true, force: true })
}
