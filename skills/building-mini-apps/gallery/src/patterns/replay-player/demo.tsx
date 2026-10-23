import { useState } from "react"
import { CheckIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useCollection } from "@/lib/mini/store"
import { cn } from "@/lib/utils"

import { ReplayPlayer } from "./replay-player"
import type {
  ReplayEvent,
  ReplayRecording,
  ReplaySnapshot,
  ReplayTab,
} from "./types"

type Screen = "home" | "recipes" | "recipe" | "list"

type Page = {
  screen: Screen
  saved?: boolean
  ticked?: number
  banner?: string
}

type Preview = "live" | "empty" | "loading" | "error"

const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]
const REPLAYS = [
  { id: "session-4", label: "Participant 4 (2 errors)" },
  { id: "session-7", label: "Participant 7 (no errors)" },
]
const BASE = "https://larder.example"

const snap = (id: string, at: number, path: string, state: Page): ReplaySnapshot<Page> => ({
  id,
  at,
  url: `${BASE}${path}`,
  state,
})

const click = (
  id: string,
  at: number,
  selector: string,
  x: number,
  y: number
): ReplayEvent => ({ id, at, kind: "click", label: "Click", detail: selector, point: { x, y } })

const nav = (id: string, at: number, label: string, path: string): ReplayEvent => ({
  id,
  at,
  kind: "navigation",
  label,
  detail: path,
})

const SEED: ReplayRecording<Page>[] = [
  {
    id: "session-4",
    user: "Participant 4",
    meta: "Desktop browser",
    whenLabel: "4 minutes ago",
    durationMs: 90_000,
    snapshots: [
      snap("s1", 0, "/", { screen: "home" }),
      snap("s2", 8000, "/recipes", { screen: "recipes" }),
      snap("s3", 21_000, "/recipes/lemon-orzo", { screen: "recipe" }),
      snap("s4", 34_000, "/recipes/lemon-orzo", { screen: "recipe", saved: true }),
      snap("s5", 41_000, "/shopping-list", { screen: "list", ticked: 0 }),
      snap("s6", 52_500, "/shopping-list", { screen: "list", ticked: 2 }),
      snap("s7", 55_000, "/shopping-list", {
        screen: "list",
        ticked: 2,
        banner: "Couldn't save the list",
      }),
      snap("s8", 63_000, "/recipes", { screen: "recipes" }),
      snap("s9", 80_000, "/shopping-list", { screen: "list", ticked: 2 }),
    ],
    events: [
      nav("n0", 0, "Page load", "/"),
      click("c1", 5500, "input#search", 50, 30),
      click("c2", 7800, "a.nav-recipes", 38, 10),
      nav("n1", 8000, "Navigation", "/recipes"),
      click("c3", 18_200, "li.card:nth-child(2)", 50, 55),
      nav("n2", 21_000, "Navigation", "/recipes/lemon-orzo"),
      click("c4", 29_000, "button.add-to-list", 70, 72),
      click("c5", 33_800, "button.save-recipe", 82, 28),
      click("c6", 39_500, "a.nav-list", 62, 10),
      nav("n3", 41_000, "Navigation", "/shopping-list"),
      click("c7", 50_000, "li.item:nth-child(1) input", 14, 42),
      click("c8", 52_000, "li.item:nth-child(2) input", 14, 54),
      click("c9", 54_600, "button.save-list", 76, 84),
      {
        id: "e1",
        at: 55_100,
        kind: "error",
        label: "TypeError",
        detail: "Cannot read properties of undefined (reading 'items')",
      },
      click("c10", 60_200, "button.retry", 50, 46),
      {
        id: "e2",
        at: 60_300,
        kind: "error",
        label: "RequestError",
        detail: "PUT /api/shopping-list failed with status 500",
      },
      click("c11", 62_800, "a.nav-recipes", 38, 10),
      nav("n4", 63_000, "Navigation", "/recipes"),
      click("c12", 79_800, "a.nav-list", 62, 10),
      nav("n5", 80_000, "Navigation", "/shopping-list"),
      { id: "l1", at: 400, kind: "console", label: "App ready", detail: "build 142" },
      { id: "l2", at: 8100, kind: "console", label: "Fetched recipes", detail: "12 items" },
      { id: "l3", at: 34_100, kind: "console", label: "Slow render", detail: "RecipeCard took 180 ms" },
      { id: "l4", at: 55_100, kind: "console", label: "Uncaught TypeError", detail: "list.items is undefined", tone: "error" },
      { id: "l5", at: 60_300, kind: "console", label: "Save list failed", detail: "status 500", tone: "error" },
      { id: "r1", at: 8000, kind: "network", label: "GET /api/recipes", detail: "200 · 84 ms · 12 kB" },
      { id: "r2", at: 21_100, kind: "network", label: "GET /api/recipes/lemon-orzo", detail: "200 · 62 ms · 4 kB" },
      { id: "r3", at: 33_900, kind: "network", label: "POST /api/favorites", detail: "201 · 120 ms · 0.2 kB" },
      { id: "r4", at: 41_100, kind: "network", label: "GET /api/shopping-list", detail: "200 · 45 ms · 1 kB" },
      { id: "r5", at: 54_700, kind: "network", label: "PUT /api/shopping-list", detail: "500 · 310 ms · 0.1 kB", tone: "error" },
      { id: "r6", at: 60_250, kind: "network", label: "PUT /api/shopping-list", detail: "500 · 295 ms · 0.1 kB", tone: "error" },
      { id: "r7", at: 63_100, kind: "network", label: "GET /api/recipes", detail: "200 · 77 ms · 12 kB" },
      { id: "r8", at: 80_100, kind: "network", label: "GET /api/shopping-list", detail: "200 · 41 ms · 1 kB" },
      { id: "t1", at: 12_000, kind: "note", label: "Looks for dinner ideas first" },
      { id: "t2", at: 29_000, kind: "note", label: "Expected the add button to confirm", detail: "no message appeared" },
      { id: "t3", at: 55_200, kind: "note", label: "Sighs after the save failure" },
    ],
  },
  {
    id: "session-7",
    user: "Participant 7",
    meta: "Desktop browser",
    whenLabel: "1 hour ago",
    durationMs: 45_000,
    snapshots: [
      snap("p1", 0, "/", { screen: "home" }),
      snap("p2", 9000, "/recipes", { screen: "recipes" }),
      snap("p3", 18_000, "/recipes/lemon-orzo", { screen: "recipe" }),
      snap("p4", 30_000, "/recipes/lemon-orzo", { screen: "recipe", saved: true }),
    ],
    events: [
      nav("pn0", 0, "Page load", "/"),
      click("pc1", 6000, "a.nav-recipes", 38, 10),
      nav("pn1", 9000, "Navigation", "/recipes"),
      click("pc2", 15_500, "li.card:nth-child(2)", 50, 55),
      nav("pn2", 18_000, "Navigation", "/recipes/lemon-orzo"),
      click("pc3", 29_400, "button.save-recipe", 82, 28),
      click("pc4", 38_000, "button.add-to-list", 70, 72),
      { id: "pl1", at: 300, kind: "console", label: "App ready", detail: "build 142" },
      { id: "pr1", at: 9100, kind: "network", label: "GET /api/recipes", detail: "200 · 79 ms · 12 kB" },
      { id: "pr2", at: 18_100, kind: "network", label: "GET /api/recipes/lemon-orzo", detail: "200 · 58 ms · 4 kB" },
      { id: "pr3", at: 29_500, kind: "network", label: "POST /api/favorites", detail: "201 · 111 ms · 0.2 kB" },
    ],
  },
]

const EXTRA_TABS: ReplayTab[] = [
  { id: "notes", label: "Notes", kinds: ["note"], emptyTitle: "No notes on this replay" },
]

const HINTS = [
  "Space play or pause",
  "Left/Right seek 5s",
  "Click a time in a list to seek",
  "On the slider: arrows 5s, Home/End, PageUp/PageDown 30s",
  "Tab to reach the controls",
]

function Block({ className }: { className?: string }) {
  return <div className={cn("rounded-sm bg-muted", className)} />
}

function PageSketch({ page }: { page: Page }) {
  const nav = (
    <div className="flex items-center gap-3 border-b px-3 py-2 text-xs">
      <span className="font-semibold">Larder</span>
      <span className={cn(page.screen === "recipes" && "font-medium underline")}>Recipes</span>
      <span className={cn(page.screen === "list" && "font-medium underline")}>List</span>
    </div>
  )
  return (
    <div className="flex size-full flex-col bg-background text-xs">
      {nav}
      <div className="flex min-h-0 flex-1 flex-col gap-1.5 p-3">
        {page.screen === "home" ? (
          <>
            <p className="text-sm font-semibold">What are we cooking?</p>
            <div className="rounded-md border px-2 py-1.5 text-muted-foreground">Search recipes</div>
            <div className="grid grid-cols-3 gap-2">
              <Block className="h-14" />
              <Block className="h-14" />
              <Block className="h-14" />
            </div>
          </>
        ) : null}
        {page.screen === "recipes" ? (
          <>
            <p className="text-sm font-semibold">Recipes</p>
            <div className="grid grid-cols-3 gap-2">
              {["Tomato soup", "Lemon orzo", "Barley salad", "Flatbread", "Dal", "Pickles"].map(
                (name) => (
                  <div key={name} className="flex flex-col gap-1 rounded-md border p-1.5">
                    <Block className="h-8" />
                    <span className="truncate">{name}</span>
                  </div>
                )
              )}
            </div>
          </>
        ) : null}
        {page.screen === "recipe" ? (
          <>
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">Lemon orzo</p>
              <span className="rounded-md border px-2 py-0.5">
                {page.saved ? "Saved" : "Save"}
              </span>
            </div>
            <Block className="h-12" />
            <Block className="h-2 w-3/4" />
            <Block className="h-2 w-2/3" />
            <span className="w-fit rounded-md bg-primary px-2 py-1 text-primary-foreground">
              Add to list
            </span>
          </>
        ) : null}
        {page.screen === "list" ? (
          <>
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">Shopping list</p>
              <span className="rounded-md bg-primary px-2 py-0.5 text-primary-foreground">
                Save list
              </span>
            </div>
            {page.banner ? (
              <p className="rounded-md bg-[var(--mini-removed)] px-2 py-1 text-destructive">
                {page.banner}
              </p>
            ) : null}
            {["Orzo", "Lemons", "Parsley"].map((item, index) => (
              <div key={item} className="flex items-center gap-2">
                <span
                  className={cn(
                    "flex size-3.5 items-center justify-center rounded-sm border",
                    index < (page.ticked ?? 0) && "bg-primary text-primary-foreground"
                  )}
                >
                  {index < (page.ticked ?? 0) ? <CheckIcon className="size-2.5" /> : null}
                </span>
                <span>{item}</span>
              </div>
            ))}
          </>
        ) : null}
      </div>
    </div>
  )
}

export default function Demo() {
  const replays = useCollection<ReplayRecording<Page>>("replay-player-demo", SEED)
  const [preview, setPreview] = useState<Preview>("live")
  const [activeId, setActiveId] = useState("session-4")

  const status = preview === "live" ? replays.status : preview === "empty" ? "ready" : preview
  const items = preview === "empty" ? [] : replays.items

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">State preview (demo only)</span>
        <div role="group" aria-label="State preview" className="flex gap-1">
          {PREVIEWS.map((name) => (
            <Button
              key={name}
              size="xs"
              variant={preview === name ? "default" : "outline"}
              aria-pressed={preview === name}
              onClick={() => setPreview(name)}
              className="capitalize"
            >
              {name}
            </Button>
          ))}
        </div>
        <span className="ml-2 text-xs text-muted-foreground">Replay (demo only)</span>
        <div role="group" aria-label="Replay" className="flex gap-1">
          {REPLAYS.map((replay) => (
            <Button
              key={replay.id}
              size="xs"
              variant={activeId === replay.id ? "default" : "outline"}
              aria-pressed={activeId === replay.id}
              onClick={() => setActiveId(replay.id)}
            >
              {replay.label}
            </Button>
          ))}
        </div>
        <Button
          size="xs"
          variant="ghost"
          onClick={() => void replays.replaceAll(SEED)}
          className="ml-auto"
        >
          Restore sample replays
        </Button>
      </div>

      <div className="h-[40rem] shrink-0 overflow-hidden rounded-lg border">
        <ReplayPlayer
          aria-label="Usability test replay"
          items={items}
          activeId={activeId}
          status={status}
          error={new Error("Could not read the replay (simulated).")}
          onRetry={() => setPreview("live")}
          renderSnapshot={(snapshot) => <PageSketch page={snapshot.state} />}
          extraTabs={EXTRA_TABS}
          emptyTitle="No replay to show"
        />
      </div>

      <p className="text-xs text-muted-foreground">{HINTS.join(" · ")}</p>
    </div>
  )
}
