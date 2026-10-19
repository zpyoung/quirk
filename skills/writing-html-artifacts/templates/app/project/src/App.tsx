import type { ReactNode } from 'react'
import { createHashHistory, createRootRoute, createRoute, createRouter, Outlet, RouterProvider, useNavigate, useRouterState } from '@tanstack/react-router'
import { Button } from '@astryxdesign/core/Button'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, Layout, LayoutContent, LayoutHeader, VStack } from '@astryxdesign/core/Layout'
import { Tab, TabList } from '@astryxdesign/core/TabList'
import { Theme } from '@astryxdesign/core/theme'
import { neutralTheme } from '@astryxdesign/theme-neutral/built'
import { PageLayout } from './PageLayout'
import { views } from './routes'
import { nextThemeMode, setThemeMode, useThemeMode } from './theme'

function Shell() {
  const navigate = useNavigate()
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const mode = useThemeMode()
  const active = views.find((view) => view.path === pathname) ?? views[0]
  const { summary }: { summary?: ReactNode } = active

  return (
    <Layout
      height="auto"
      header={
        <LayoutHeader hasDivider label="Page header">
          <VStack gap={2} paddingBlock={3}>
            <HStack gap={2} justify="between" align="center" wrap="wrap">
              <Heading level={1}>{document.title}</Heading>
              <Button label={`Theme: ${mode}`} variant="secondary" size="sm" onClick={() => setThemeMode(nextThemeMode(mode))} />
            </HStack>
            {views.length > 1 ? (
              <TabList value={active.path} onChange={(path) => void navigate({ to: path })} role="tablist" hasDivider aria-label="Views">
                {views.map((view) => (
                  <Tab key={view.path} value={view.path} label={view.label} panelId="panel" />
                ))}
              </TabList>
            ) : null}
          </VStack>
        </LayoutHeader>
      }
      content={
        <LayoutContent label={active.label} padding={4} isScrollable={false}>
          <VStack id="panel" role="tabpanel" gap={4} paddingBlockEnd={8}>
            <PageLayout summary={summary}>
              <Outlet />
            </PageLayout>
          </VStack>
        </LayoutContent>
      }
    />
  )
}

// hash history because History API routes do not work on file://; components stay statically imported so the bundle is one chunk
const rootRoute = createRootRoute({ component: Shell })
const router = createRouter({
  routeTree: rootRoute.addChildren(
    views.map((view) => createRoute({ getParentRoute: () => rootRoute, path: view.path, component: view.component })),
  ),
  history: createHashHistory(),
})

export default function App() {
  const mode = useThemeMode()
  return (
    <Theme theme={neutralTheme} mode={mode === 'auto' ? 'system' : mode}>
      <RouterProvider router={router} />
    </Theme>
  )
}
