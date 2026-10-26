import { useEffect, useState } from "react"
import Markdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

import { ErrorState, LoadingState } from "@/components/mini/states"

const components: Components = {
  h1: (props) => <h1 className="mb-3 text-lg font-semibold tracking-tight" {...props} />,
  h2: (props) => <h2 className="mt-6 mb-2 text-sm font-semibold tracking-tight" {...props} />,
  h3: (props) => <h3 className="mt-4 mb-1 text-sm font-medium" {...props} />,
  p: (props) => <p className="my-2 text-[0.8rem] leading-relaxed" {...props} />,
  ul: (props) => <ul className="my-2 list-disc space-y-1 pl-5 text-[0.8rem]" {...props} />,
  ol: (props) => <ol className="my-2 list-decimal space-y-1 pl-5 text-[0.8rem]" {...props} />,
  a: (props) => <a className="text-primary underline underline-offset-2" {...props} />,
  pre: (props) => (
    <pre
      className="my-2 overflow-x-auto rounded-md border bg-muted p-3 font-mono text-xs leading-snug"
      {...props}
    />
  ),
  code: ({ className, ...props }) => (
    <code
      className={className ?? "rounded bg-muted px-1 py-0.5 font-mono text-[0.75rem]"}
      {...props}
    />
  ),
  table: (props) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-xs" {...props} />
    </div>
  ),
  th: (props) => (
    <th className="border-b px-2 py-1 text-left font-medium text-muted-foreground" {...props} />
  ),
  td: (props) => <td className="border-b px-2 py-1 align-top" {...props} />,
}

/** Renders a pattern's reference markdown, loaded on demand from `load`. */
export function ReferencePanel({ slug, load }: { slug: string; load?: () => Promise<string> }) {
  const [result, setResult] = useState<{ slug: string; text?: string; error?: Error }>()

  useEffect(() => {
    let cancelled = false
    if (!load) return
    load().then(
      (text) => !cancelled && setResult({ slug, text }),
      (cause) =>
        !cancelled &&
        setResult({ slug, error: cause instanceof Error ? cause : new Error(String(cause)) })
    )
    return () => {
      cancelled = true
    }
  }, [slug, load])

  if (!load) {
    return <p className="p-4 text-xs text-muted-foreground">No reference written for this pattern.</p>
  }
  if (result?.slug !== slug) return <LoadingState label="Loading reference" />
  if (result.error) return <ErrorState error={result.error} />

  return (
    <article className="p-4">
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {result.text ?? ""}
      </Markdown>
    </article>
  )
}
