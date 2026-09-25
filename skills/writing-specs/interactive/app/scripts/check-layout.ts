import { randomUUID } from 'node:crypto'
import { rm, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import ts from 'typescript'
import fixture from '../../../../../tests/fixtures/interactive/v2/stage2/logic.json'

const appRoot = fileURLToPath(new URL('../', import.meta.url))
const configPath = resolve(appRoot, 'tsconfig.json')
const configFile = ts.readConfigFile(configPath, ts.sys.readFile)
if (configFile.error) throw new Error(ts.flattenDiagnosticMessageText(configFile.error.messageText, ts.sys.newLine))
const parsedConfig = ts.parseJsonConfigFileContent(configFile.config, ts.sys, appRoot, undefined, configPath)
if (parsedConfig.errors.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(parsedConfig.errors, {
  getCanonicalFileName: (fileName) => fileName,
  getCurrentDirectory: () => appRoot,
  getNewLine: () => ts.sys.newLine,
}))

const generatedPath = resolve(appRoot, `.layout-check-fixture-${randomUUID()}.ts`)
const generatedSource = `import { layoutStateMachine } from './src/layout'
import type { LogicSpec } from './src/spec-types'

const sample = ${JSON.stringify(fixture)} satisfies LogicSpec
const machine = sample.views?.stateMachine
if (!machine) throw new Error('Sample fixture does not include a state machine.')

const layout = await layoutStateMachine(machine)
const boxes = [
  ...layout.nodes.map((node) => ({ id: node.id, x: node.x, y: node.y, width: node.width, height: node.height })),
  ...layout.edges.flatMap((edge) => edge.labels.map((label) => ({ id: label.id, x: label.x, y: label.y, width: label.width, height: label.height }))),
]

for (let leftIndex = 0; leftIndex < boxes.length; leftIndex += 1) {
  const left = boxes[leftIndex]
  if (!left) continue
  for (let rightIndex = leftIndex + 1; rightIndex < boxes.length; rightIndex += 1) {
    const right = boxes[rightIndex]
    if (!right || (left.id.startsWith('label:') && right.id.startsWith('label:') && left.id === right.id)) continue
    const intersects = left.x < right.x + right.width && left.x + left.width > right.x && left.y < right.y + right.height && left.y + left.height > right.y
    if (intersects) throw new Error(\`ELK collision: \${left.id} intersects \${right.id}.\`)
  }
}

console.log(\`ELK layout passed collision check for \${boxes.length} node and edge-label boxes.\`)
`

try {
  await writeFile(generatedPath, generatedSource, { flag: 'wx' })
  const program = ts.createProgram({ rootNames: [generatedPath], options: parsedConfig.options })
  const diagnostics = ts.getPreEmitDiagnostics(program)
  if (diagnostics.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCanonicalFileName: (fileName) => fileName,
    getCurrentDirectory: () => appRoot,
    getNewLine: () => ts.sys.newLine,
  }))
  // This generated fixture module exists only for the current check, so a static import cannot resolve it.
  await import(pathToFileURL(generatedPath).href)
} finally {
  await rm(generatedPath, { force: true })
}
