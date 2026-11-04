import libraries from '../../../vendor/libraries.json'

interface LibraryFile {
  path: string
  kind: string
}
interface LibraryVersion {
  files: LibraryFile[]
}
interface Library {
  current?: string
  versions: Record<string, LibraryVersion>
}

const KIT_TAG = /<q-[a-z]/i
const CHART_TAG = /<q-chart[\s/>]/i
const CODE_TAG = /<q-(?:code|diff)[\s/>]/i
const FLOW_TAG = /<q-flow[\s/>]/i
const SCHEMA_TAG = /<q-schema[\s/>]/i

export interface KitNeeds {
  kit: boolean
  chartjs: boolean
  highlightjs: boolean
  flow: boolean
}

/** Ports the `kitcheck.needs*` rules: which libraries a stretch of agent HTML pulls in. */
export function kitNeeds(text: string): KitNeeds {
  return {
    kit: KIT_TAG.test(text),
    chartjs: CHART_TAG.test(text),
    highlightjs: CODE_TAG.test(text),
    flow: FLOW_TAG.test(text) || SCHEMA_TAG.test(text),
  }
}

export interface LibAsset {
  kind: 'js' | 'css'
  url: string
}

function assets(name: string): LibAsset[] {
  const lib = (libraries.libraries as unknown as Record<string, Library>)[name]
  const version = lib?.current
  if (!lib || !version) throw new Error(`libraries.json has no current version of ${name}`)
  return lib.versions[version].files
    .filter((file) => file.kind === 'js' || file.kind === 'css')
    .map((file) => ({ kind: file.kind as 'js' | 'css', url: `/_quirk/lib/${name}/${version}/${file.path}` }))
}

/** Assets to load, in order, for the kit libraries a step needs: chartjs, highlightjs, flow, then kit. */
export function kitAssets(needs: KitNeeds): LibAsset[] {
  const names = [
    ...(needs.chartjs ? ['chartjs'] : []),
    ...(needs.highlightjs ? ['highlightjs'] : []),
    ...(needs.flow ? ['flow'] : []),
    'kit',
  ]
  return names.flatMap(assets)
}

export function mermaidAssets(): LibAsset[] {
  return assets('mermaid')
}

/** The ELK layout bundle `q-flow` uses; it sets `window.quirkFlow.ELK`. */
export function flowAssets(): LibAsset[] {
  return assets('flow')
}

const loaded = new Map<string, Promise<void>>()

function load(asset: LibAsset): Promise<void> {
  const cached = loaded.get(asset.url)
  if (cached) return cached
  const promise = new Promise<void>((resolve, reject) => {
    if (asset.kind === 'css') {
      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = asset.url
      link.onload = () => resolve()
      link.onerror = () => reject(new Error(`failed to load ${asset.url}`))
      document.head.appendChild(link)
      return
    }
    const script = document.createElement('script')
    script.src = asset.url
    script.async = false
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`failed to load ${asset.url}`))
    document.head.appendChild(script)
  })
  promise.catch(() => loaded.delete(asset.url))
  loaded.set(asset.url, promise)
  return promise
}

/** Loads assets one after another, because kit.js reads window.Chart and window.quirkFlow when it starts. */
export async function loadAssets(list: LibAsset[]): Promise<void> {
  for (const asset of list) await load(asset)
}
