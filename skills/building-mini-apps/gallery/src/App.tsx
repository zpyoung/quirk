import { Suspense, lazy, useMemo, type ComponentType } from "react"

import { AppShell } from "@/components/mini/app-shell"
import { EmptyState, LoadingState } from "@/components/mini/states"
import { cn } from "@/lib/utils"
import { ErrorBoundary } from "@/gallery/error-boundary"
import { ReferencePanel } from "@/gallery/reference-panel"
import { StylePicker } from "@/gallery/style-picker"
import { ThemeToggle } from "@/gallery/theme-toggle"
import { useHashRoute } from "@/gallery/use-hash-route"

const demoModules = import.meta.glob<{ default: ComponentType }>("./patterns/*/demo.tsx")
const referenceModules = import.meta.glob<string>("../../references/patterns/*.md", {
  query: "?raw",
  import: "default",
})

const slugOf = (path: string) => path.split("/").slice(-2, -1)[0]
const referenceSlugOf = (path: string) => path.split("/").pop()!.replace(/\.md$/, "")

const demos = Object.entries(demoModules)
  .map(([path, load]) => ({ slug: slugOf(path), Demo: lazy(load) }))
  .sort((a, b) => a.slug.localeCompare(b.slug))

const references = new Map(
  Object.entries(referenceModules).map(([path, load]) => [referenceSlugOf(path), load])
)

export function App() {
  const route = useHashRoute()
  const current = useMemo(
    () => (route ? demos.find((d) => d.slug === route) : demos[0]),
    [route]
  )

  const nav = (
    <nav aria-label="Patterns" className="flex flex-col gap-0.5">
      {demos.map(({ slug }) => (
        <a
          key={slug}
          href={`#/${slug}`}
          aria-current={slug === current?.slug ? "page" : undefined}
          className={cn(
            "rounded-md px-2 py-1 text-xs hover:bg-sidebar-accent",
            slug === current?.slug && "bg-sidebar-accent font-medium"
          )}
        >
          {slug}
        </a>
      ))}
    </nav>
  )

  let body
  if (demos.length === 0) {
    body = (
      <EmptyState
        title="No patterns yet"
        description="Add a block under src/patterns/<pattern>/ with a demo.tsx and it appears here."
      />
    )
  } else if (!current) {
    body = (
      <EmptyState
        title={`No pattern named "${route}"`}
        description="Pick one from the list on the left."
      />
    )
  } else {
    const { Demo, slug } = current
    body = (
      <div className="grid min-h-full lg:h-full lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <section aria-label={`${slug} demo`} className="min-w-0 lg:overflow-auto">
          <ErrorBoundary resetKey={slug}>
            <Suspense fallback={<LoadingState label="Loading demo" />}>
              <Demo />
            </Suspense>
          </ErrorBoundary>
        </section>
        <aside
          aria-label={`${slug} reference`}
          className="min-w-0 border-t bg-card lg:overflow-auto lg:border-t-0 lg:border-l"
        >
          <ReferencePanel slug={slug} load={references.get(slug)} />
        </aside>
      </div>
    )
  }

  return (
    <AppShell title="Mini-app patterns" sidebar={nav} toolbar={
        <div className="flex items-center gap-2">
          <StylePicker />
          <ThemeToggle />
        </div>
      }>
      {body}
    </AppShell>
  )
}

export default App
