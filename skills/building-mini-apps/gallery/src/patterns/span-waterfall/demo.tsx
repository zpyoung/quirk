import { useState } from "react"

import { useCollection } from "@/lib/mini/store"
import { Button } from "@/components/ui/button"

import { SpanWaterfall } from "./span-waterfall"
import type { Span, WaterfallMarker, WaterfallStat } from "./types"

type Preview = "live" | "empty" | "loading" | "error"

const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]

type Extra = { errors?: string[]; attributes?: Record<string, string> }

// seconds in the table, milliseconds in the data
const span = (
  id: string,
  parentId: string | null,
  op: string,
  description: string,
  start: number,
  duration: number,
  extra: Extra = {}
): Span => ({ id, parentId, op, description, start: start * 1000, duration: duration * 1000, ...extra })

const on = (runner: string, more: Record<string, string> = {}): Extra => ({
  attributes: { runner, ...more },
})

const SEED: Span[] = [
  span("s01", null, "pipeline.run", "ship-web #482", 0, 700, { attributes: { trigger: "merge to main" } }),
  span("s02", "s01", "setup.checkout", "fetch source at 9f3c1a2", 0, 4.2, on("build-pool-1")),
  span("s03", "s02", "setup.fetch", "download 412 objects", 0.3, 3.4, on("build-pool-1", { "bytes": "18.2 MB" })),
  span("s04", "s01", "setup.restore", "restore package cache", 4.3, 6.1, on("build-pool-1", { "cache.hit": "true" })),
  span("s05", "s01", "setup.install", "install packages", 10.5, 38, on("build-pool-1")),
  span("s06", "s05", "setup.fetch", "resolve 1,284 packages", 10.7, 9.8, on("build-pool-1", { "bytes": "41.7 MB" })),
  span("s07", "s05", "setup.link", "link workspace packages", 20.6, 26, on("build-pool-1")),
  span("s08", "s01", "check.static", "static checks", 48.6, 21.3, on("build-pool-2")),
  span("s09", "s08", "check.rule", "format check", 48.8, 7.1, on("build-pool-2")),
  span("s10", "s08", "check.rule", "type check", 56, 13.4, on("build-pool-2")),
  span("s11", "s01", "check.unit", "unit tests, 4 shards", 48.7, 94, on("build-pool-3")),
  span("s12", "s11", "check.shard", "shard 1 of 4: 312 tests", 48.9, 71, on("build-pool-3")),
  span("s13", "s11", "check.shard", "shard 2 of 4: 305 tests", 48.9, 88, on("build-pool-3")),
  span("s14", "s11", "check.shard", "shard 3 of 4: 298 tests", 49, 62, on("build-pool-3")),
  span("s15", "s11", "check.shard", "shard 4 of 4: 310 tests", 49, 92.7, on("build-pool-3")),
  span("s16", "s01", "check.e2e", "browser tests", 143, 118, on("build-pool-4")),
  span("s17", "s16", "check.case", "checkout flow", 143.5, 41.2, {
    errors: ["timeout waiting for #pay-button after 30000ms"],
    attributes: { runner: "build-pool-4", attempt: "1" },
  }),
  span("s18", "s16", "check.case", "retry: checkout flow", 185, 38.4, on("build-pool-4", { attempt: "2" })),
  span("s19", "s16", "check.case", "search results", 143.6, 52),
  span("s20", "s16", "check.case", "profile settings", 223.8, 36, on("build-pool-4", { attempt: "1" })),
  span("s21", "s01", "build.bundle", "production bundle", 262, 71, on("build-pool-1")),
  span("s22", "s21", "build.compile", "compile 940 modules", 262.4, 49, on("build-pool-1")),
  span("s23", "s21", "build.minify", "minify and hash assets", 312, 20.5, on("build-pool-1")),
  span("s24", "s01", "build.image", "package release image", 334, 46, on("build-pool-2")),
  span("s25", "s24", "build.layer", "base layer (cached)", 334.5, 2, on("build-pool-2", { "cache.hit": "true" })),
  span("s26", "s24", "build.layer", "app layer", 336.6, 41, on("build-pool-2", { "cache.hit": "false" })),
  span("s27", "s01", "ship.upload", "upload image to registry", 560, 38, on("deploy-1", { region: "north-1" })),
  span(
    "s28",
    "s01",
    "ship.rollout",
    "roll out to 12 hosts in 3 batches, waiting for each batch to report healthy before starting the next, with automatic rollback if two probes fail in a row",
    598,
    70,
    on("deploy-1", { region: "north-1" })
  ),
  span("s29", "s28", "ship.batch", "batch 1 of 3", 598.5, 20, on("deploy-1", { hosts: "4" })),
  span("s30", "s28", "ship.batch", "batch 2 of 3", 619, 22, on("deploy-1", { hosts: "4" })),
  span("s31", "s28", "ship.batch", "batch 3 of 3", 642, 25, on("deploy-1", { hosts: "4" })),
  span("s32", "s01", "ship.verify", "health probes", 668, 28, on("deploy-1")),
  span("s33", "s32", "ship.probe", "probe /health on 12 hosts", 668.5, 6, on("deploy-1")),
  span("s34", "s32", "ship.probe", "probe /checkout on host 7", 675, 10, {
    errors: ["503 service unavailable", "503 service unavailable"],
    attributes: { runner: "deploy-1", host: "host-7" },
  }),
  span("s35", "s01", "ship.mark", "release tagged", 697, 0, on("deploy-1")),
]

const STATS: WaterfallStat[] = [
  { label: "Queue wait", value: "1.2s" },
  { label: "Cache", value: "warm" },
  { label: "Retried tests", value: "1", tone: "bad" },
]

const MARKERS: WaterfallMarker[] = [{ label: "Build starts", at: 262_000 }]

const HINTS = [
  "Up/Down move between spans",
  "Left/Right collapse, expand, or step to parent or child",
  "Enter opens the panel, Esc closes it",
  "Home/End first or last span",
  "Click a row to open or swap the panel",
  "Pin an attribute in the panel to make it a column",
  "Enter in search steps through matches",
]

export default function Demo() {
  const spans = useCollection<Span>("span-waterfall-demo", SEED)
  const [preview, setPreview] = useState<Preview>("live")

  const restore = () => {
    setPreview("live")
    void spans.replaceAll(SEED)
  }

  const status = preview === "live" ? spans.status : preview === "empty" ? "ready" : preview
  const items = preview === "empty" ? [] : spans.items

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
      </div>

      <div className="min-h-[34rem] flex-1 overflow-hidden rounded-lg border">
        <SpanWaterfall
          aria-label="Release pipeline trace"
          title="ship-web #482"
          subtitle="Release pipeline, commit 9f3c1a2"
          spans={items}
          status={status}
          error={new Error("Could not read the sample trace (simulated).")}
          onRetry={() => setPreview("live")}
          stats={STATS}
          markers={MARKERS}
          defaultPinnedKeys={["runner"]}
          emptyAction={{ label: "Restore sample trace", onClick: restore }}
        />
      </div>

      <p className="text-xs text-muted-foreground">{HINTS.join(" · ")}</p>
    </div>
  )
}
