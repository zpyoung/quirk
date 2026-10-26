import { useState } from "react"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useCollection } from "@/lib/mini/store"

import { ActionPalette } from "./action-palette"
import type { PaletteAction } from "./types"

type SavedLink = {
  id: string
  title: string
  url: string
  kind: "Link" | "Note"
  pinned: boolean
  folder: string
}

type Preview = "live" | "empty" | "loading" | "error"

const FOLDERS = ["Reading", "Reference", "Archive"]

const seed: SavedLink[] = [
  { id: "l1", title: "Notes on keyboard-first interfaces", url: "https://example.com/keyboard-first", kind: "Note", pinned: true, folder: "Reading" },
  { id: "l2", title: "Quarterly planning template", url: "https://example.org/planning-template", kind: "Link", pinned: true, folder: "Reference" },
  { id: "l3", title: "How indexes speed up a query", url: "https://example.net/indexes", kind: "Link", pinned: false, folder: "Reading" },
  { id: "l4", title: "Release checklist", url: "https://example.com/release-checklist", kind: "Note", pinned: false, folder: "Reference" },
  { id: "l5", title: "A very long title that keeps going well past the edge of the row so you can see how truncation behaves with the full text in the tooltip", url: "https://example.org/long-title-one", kind: "Link", pinned: false, folder: "Reading" },
  { id: "l6", title: "Color contrast reference", url: "https://example.net/contrast", kind: "Link", pinned: false, folder: "Reference" },
  { id: "l7", title: "Meeting notes, design review", url: "https://example.com/design-review", kind: "Note", pinned: false, folder: "Archive" },
  { id: "l8", title: "Another remarkably long saved title that is here to show how the action panel header truncates a name that does not fit", url: "https://example.org/long-title-two", kind: "Note", pinned: false, folder: "Reading" },
  { id: "l9", title: "Regex cheat sheet", url: "https://example.net/regex", kind: "Link", pinned: false, folder: "Reference" },
  { id: "l10", title: "Reading list for the weekend", url: "https://example.com/weekend", kind: "Note", pinned: false, folder: "Reading" },
  { id: "l11", title: "Local-first software essay", url: "https://example.org/local-first", kind: "Link", pinned: false, folder: "Archive" },
  { id: "l12", title: "Shell one-liners worth keeping", url: "https://example.net/one-liners", kind: "Link", pinned: false, folder: "Reference" },
]

const hostOf = (url: string) => {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export default function Demo() {
  const links = useCollection<SavedLink>("action-palette-demo", seed)
  const [preview, setPreview] = useState<Preview>("live")
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const live = preview === "live"
  const status =
    preview === "loading" ? "loading" : preview === "error" ? "error" : links.status
  const items = live ? [...links.items].sort((a, b) => Number(b.pinned) - Number(a.pinned)) : []

  function getActions(link: SavedLink, selection: SavedLink[]): PaletteAction<SavedLink>[] {
    const many = selection.length > 1
    const allPinned = selection.every((item) => item.pinned)
    const open: PaletteAction<SavedLink> = {
      id: "open",
      title: "Open",
      section: "use",
      run: (item) => void window.open(item.url, "_blank", "noopener,noreferrer"),
    }
    return [
      ...(many ? [] : [open]),
      {
        id: "copy",
        title: many ? "Copy URLs" : "Copy URL",
        section: "use",
        pending: "Copying URL…",
        successMessage: many ? `${selection.length} URLs copied` : "URL copied",
        run: (item) => navigator.clipboard.writeText(item.url),
        runMany: (picked) => navigator.clipboard.writeText(picked.map((item) => item.url).join("\n")),
      },
      {
        id: "pin",
        title: (many ? allPinned : link.pinned) ? "Unpin" : "Pin",
        section: "organize",
        shortcut: "mod+shift+p",
        run: (item) => links.update(item.id, { pinned: !item.pinned }),
        runMany: async (picked) => {
          for (const item of picked) await links.update(item.id, { pinned: !allPinned })
        },
      },
      {
        id: "move",
        title: "Move to…",
        section: "organize",
        children: FOLDERS.map((folder) => ({
          id: `move-${folder}`,
          title: folder,
          successMessage: many ? `${selection.length} moved to ${folder}` : `Moved to ${folder}`,
          run: (item: SavedLink) => links.update(item.id, { folder }),
        })),
      },
      {
        id: "delete",
        title: many ? `Delete ${selection.length}` : "Delete",
        destructive: true,
        shortcut: "mod+backspace",
        pending: "Deleting…",
        successMessage: "Deleted",
        run: async (item) => {
          await pause(600)
          await links.remove(item.id)
        },
        runMany: async (picked) => {
          await pause(600)
          for (const item of picked) await links.remove(item.id)
          setSelectedIds([])
        },
      },
    ]
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span id="action-palette-preview-label" className="text-xs text-muted-foreground">
          Preview state
        </span>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={preview}
          onValueChange={(value) => value && setPreview(value as Preview)}
          aria-labelledby="action-palette-preview-label"
        >
          {(["live", "empty", "loading", "error"] as const).map((value) => (
            <ToggleGroupItem key={value} value={value} aria-label={`Show ${value} state`}>
              {value}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>

      <div className="h-[32rem] max-w-3xl">
        <ActionPalette
          items={items}
          status={status}
          error={preview === "error" ? new Error("Could not read saved links") : links.error}
          onRetry={() => setPreview("live")}
          getActions={getActions}
          selectedIds={live ? selectedIds : []}
          onSelectedIdsChange={setSelectedIds}
          getSubtitle={(link) => hostOf(link.url)}
          getMeta={(link) => link.kind}
          getSearchText={(link) => `${link.url} ${link.folder}`}
          getSection={(link) => (link.pinned ? "Pinned" : "Saved")}
          onCreate={
            live
              ? (title) =>
                  void links.add({
                    id: crypto.randomUUID(),
                    title,
                    url: `https://example.com/${encodeURIComponent(title.toLowerCase().replace(/\s+/g, "-"))}`,
                    kind: "Link",
                    pinned: false,
                    folder: "Reading",
                  })
              : undefined
          }
          placeholder="Search saved links…"
          footerLabel="Saved links"
          emptyState={{
            title: "No saved links yet",
            description: "Links you save show up here.",
          }}
        />
      </div>

      <p className="max-w-3xl text-xs text-muted-foreground">
        ↑ ↓ move · ↵ run the first action · ⌘K actions · ⇧⌘X check the highlighted row · ⇧↑ ⇧↓ check
        while moving · Esc backs out, then clears the query, then the checked rows
      </p>
    </div>
  )
}
