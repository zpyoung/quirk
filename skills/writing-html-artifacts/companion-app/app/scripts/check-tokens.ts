import { execFileSync } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const appRoot = fileURLToPath(new URL('../', import.meta.url))
const generated = execFileSync('python3', [resolve(appRoot, 'scripts/gen_tokens.py')], { encoding: 'utf8' })
const committed = await readFile(resolve(appRoot, 'src/quirk-tokens.css'), 'utf8')

if (generated === committed) {
  console.log('quirk-tokens.css matches the house tokens.')
} else {
  console.error('src/quirk-tokens.css is stale; run pnpm run tokens')
  process.exitCode = 1
}
