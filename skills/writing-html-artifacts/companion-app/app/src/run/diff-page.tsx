import { useEffect, useState, type JSX } from 'react'
import { fetchDiff } from './api'
import type { DiffFile, RunDiff } from './types'

const SHORT_SHA = 7

function lineKind(line: string): 'add' | 'del' | undefined {
  if (line.startsWith('+')) return 'add'
  if (line.startsWith('-')) return 'del'
  return undefined
}

function Patch({ patch }: { patch: string }): JSX.Element {
  const lines = patch.split('\n')
  if (lines[lines.length - 1] === '') lines.pop()
  return (
    <pre className="run-diff-patch">
      {lines.map((line, index) => (
        <span key={index} className="run-diff-line" data-line={lineKind(line)}>{`${line}\n`}</span>
      ))}
    </pre>
  )
}

function FileSection({ file }: { file: DiffFile }): JSX.Element {
  return (
    <section className="run-diff-file">
      <h3>
        <span className="run-diff-path">{file.path}</span>
        <span className="run-diff-status" data-status={file.status}>{file.status}</span>
      </h3>
      {file.binary ? <p>Binary file</p> : file.patch ? <Patch patch={file.patch} /> : <p>No textual changes</p>}
    </section>
  )
}

/** Read-only render of one task's diff; `null` means the companion has none for the task. */
export function DiffView({ diff, task }: { diff: RunDiff | null; task: string }): JSX.Element {
  if (!diff) return <p>{`No diff for ${task}.`}</p>
  return (
    <div className="run-diff">
      <p className="run-diff-meta">
        <strong>{diff.task}</strong>
        <span>{`base ${diff.base.slice(0, SHORT_SHA)}`}</span>
        <span>{`head ${diff.head ? diff.head.slice(0, SHORT_SHA) : 'working tree'}`}</span>
        <span>{diff.source === 'commit' ? 'committed' : 'in progress'}</span>
      </p>
      {diff.truncated ? <p className="run-diff-truncated">Diff truncated at 1 MiB.</p> : null}
      {diff.files.map((file) => (
        <FileSection key={file.path} file={file} />
      ))}
    </div>
  )
}

/** Standalone page for one task's diff; loads on mount and on Refresh. */
export function DiffPage({ task }: { task: string }): JSX.Element {
  const [diff, setDiff] = useState<RunDiff | null | undefined>(undefined)
  const [reloads, setReloads] = useState(0)

  useEffect(() => {
    let current = true
    void fetchDiff(task).then((result) => {
      if (current) setDiff(result)
    })
    return () => {
      current = false
    }
  }, [task, reloads])

  return (
    <main id="main" className="run-diff-page" data-run-part="diff-page" tabIndex={-1}>
      <header className="run-diff-header">
        <h1>{`Diff for ${task}`}</h1>
        <button type="button" onClick={() => setReloads((n) => n + 1)}>
          Refresh
        </button>
      </header>
      {diff === undefined ? <p role="status">Loading diff</p> : <DiffView diff={diff} task={task} />}
    </main>
  )
}
