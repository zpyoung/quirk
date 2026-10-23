import { useState } from "react"

import { Button } from "@/components/ui/button"
import type { Collection } from "@/lib/mini/store"

import { StagedTable, StagedTableView } from "./staged-table"
import type { StagedColumn } from "./types"

type Gear = { id: string; title: string; category: string; qty: number; location: string }

// rename to the app's domain; rows live in IndexedDB under this name
const COLLECTION = "staged-table-edit-demo"

const CATEGORIES = ["Camping", "Cooking", "Light", "Clothing", "Tools"]

const columns: StagedColumn<Gear>[] = [
  { key: "title", label: "Name", width: 220, placeholder: "Name this item" },
  { key: "category", label: "Category", type: "select", options: CATEGORIES, width: 120 },
  { key: "qty", label: "Qty", type: "number", width: 70 },
  { key: "location", label: "Location", width: 150, placeholder: "Where is it?" },
]

const seed: Gear[] = [
  { id: "g1", title: "Two-person tent", category: "Camping", qty: 1, location: "Garage" },
  { id: "g2", title: "Camp stove", category: "Cooking", qty: 2, location: "Garage" },
  { id: "g3", title: "Headlamp", category: "Light", qty: 6, location: "Hall closet" },
  { id: "g4", title: "Sleeping bag, 20 degree down, mummy cut, with compression sack and storage bag", category: "Camping", qty: 3, location: "Attic" },
  { id: "g5", title: "Fuel canister", category: "Cooking", qty: 4, location: "Shed" },
  { id: "g6", title: "Rain shell", category: "Clothing", qty: 2, location: "Hall closet" },
  { id: "g7", title: "Cook pot", category: "Cooking", qty: 1, location: "Kitchen" },
  { id: "g8", title: "Lantern", category: "Light", qty: 2, location: "Garage" },
  { id: "g9", title: "Multi-tool", category: "Tools", qty: 3, location: "Toolbox" },
  { id: "g10", title: "Sleeping pad", category: "Camping", qty: 3, location: "Attic" },
  { id: "g11", title: "Wool socks", category: "Clothing", qty: 8, location: "Dresser" },
  { id: "g12", title: "Tent stakes", category: "Camping", qty: 24, location: "Garage" },
]

const newItem = (id: string): Gear => ({ id, title: "", category: CATEGORIES[0], qty: 1, location: "" })

type Preview = "live" | "empty" | "loading" | "error"
const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]

const noopWrites: Pick<Collection<Gear>, "add" | "update" | "remove"> = {
  add: async () => {},
  update: async () => {},
  remove: async () => {},
}

const previewStore: Record<Exclude<Preview, "live">, Pick<Collection<Gear>, "items" | "status" | "error" | "add" | "update" | "remove">> = {
  empty: { items: [], status: "ready", ...noopWrites },
  loading: { items: [], status: "loading", ...noopWrites },
  error: { items: [], status: "error", error: new Error("The saved rows could not be read."), ...noopWrites },
}

export default function Demo() {
  const [preview, setPreview] = useState<Preview>("live")

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        role="group"
        aria-label="Preview state"
        className="flex items-center gap-1 border-b px-2 py-1"
      >
        <span className="mr-1 text-xs text-muted-foreground">Preview state</span>
        {PREVIEWS.map((name) => (
          <Button
            key={name}
            size="xs"
            variant={preview === name ? "secondary" : "ghost"}
            aria-pressed={preview === name}
            onClick={() => setPreview(name)}
          >
            {name}
          </Button>
        ))}
      </div>
      <div className="min-h-0 flex-1">
        {preview === "live" ? (
          <StagedTable<Gear> collection={COLLECTION} seed={seed} columns={columns} newItem={newItem} />
        ) : (
          <StagedTableView<Gear> store={previewStore[preview]} columns={columns} newItem={newItem} />
        )}
      </div>
    </div>
  )
}
