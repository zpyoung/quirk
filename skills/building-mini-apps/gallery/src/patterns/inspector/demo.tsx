import { useState } from "react"

import { EmptyState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { useCollection } from "@/lib/mini/store"
import { cn } from "@/lib/utils"

import { Inspector } from "./index"
import type { InspectorItem, InspectorSchema } from "./index"

type PosterItem = InspectorItem & {
  type: "frame" | "text" | "shape"
  x: number
  y: number
  w: number
  h: number
  fill?: string
  text?: string
  fontSize?: number
  align?: string
  shadow?: boolean
  blur?: number
}

const FILLS = [
  { value: "background", label: "Background" },
  { value: "card", label: "Card" },
  { value: "muted", label: "Muted" },
  { value: "secondary", label: "Secondary" },
  { value: "accent", label: "Accent" },
  { value: "primary", label: "Primary" },
]

const frame = (
  id: string,
  title: string,
  parentId: string | null,
  x: number,
  y: number,
  w: number,
  h: number,
  fill: string
): PosterItem => ({ id, title, type: "frame", parentId, x, y, w, h, fill })

const text = (
  id: string,
  title: string,
  parentId: string,
  x: number,
  y: number,
  w: number,
  h: number,
  copy: string,
  fontSize: number
): PosterItem => ({
  id,
  title,
  type: "text",
  parentId,
  x,
  y,
  w,
  h,
  text: copy,
  fontSize,
  align: "left",
})

const shape = (
  id: string,
  title: string,
  parentId: string,
  x: number,
  y: number,
  w: number,
  h: number,
  fill: string
): PosterItem => ({ id, title, type: "shape", parentId, x, y, w, h, fill })

const seed: PosterItem[] = [
  frame("poster", "Open Studio Poster", null, 0, 0, 320, 440, "card"),
  frame("header", "Header", "poster", 0, 0, 320, 104, "muted"),
  text("title", "Title", "header", 20, 16, 232, 40, "Open Studio Weekend", 22),
  text(
    "subtitle",
    "Subtitle",
    "header",
    20,
    62,
    220,
    24,
    "Painters, potters and printmakers",
    12
  ),
  shape("mark", "Corner mark", "header", 252, 20, 48, 48, "primary"),
  shape("photo", "Photo", "poster", 20, 124, 280, 164, "accent"),
  text(
    "caption",
    "Caption: work in progress from the north-light studio on the second floor, shown by kind permission",
    "poster",
    20,
    298,
    280,
    36,
    "Work in progress from the north-light studio",
    11
  ),
  frame("footer", "Footer", "poster", 0, 356, 320, 84, "muted"),
  text("date", "Date", "footer", 20, 372, 140, 24, "12 and 13 April", 14),
  text(
    "venue",
    "Venue",
    "footer",
    20,
    400,
    200,
    20,
    "The Mill, Canal Street",
    11
  ),
  shape("badge", "Free entry badge", "footer", 244, 372, 56, 56, "secondary"),
  shape("rule", "Divider", "poster", 20, 342, 280, 4, "primary"),
  frame("back", "Back page", null, 344, 0, 320, 440, "card"),
  text(
    "map",
    "Map note",
    "back",
    364,
    20,
    280,
    60,
    "Parking is behind the mill. Step-free entrance on the east side.",
    13
  ),
]

const schema: InspectorSchema<PosterItem> = {
  frame: [positionSection(), layoutSection(), fillSection(), shadowSection()],
  text: [
    positionSection(),
    layoutSection(),
    {
      id: "text",
      title: "Text",
      fields: [
        { key: "text", label: "Content", kind: "text" },
        {
          key: "fontSize",
          label: "Size",
          kind: "number",
          unit: "px",
          min: 8,
          max: 96,
        },
        {
          key: "align",
          label: "Align",
          kind: "select",
          options: [
            { value: "left", label: "Left" },
            { value: "center", label: "Center" },
            { value: "right", label: "Right" },
          ],
        },
      ],
    },
    shadowSection(),
  ],
  shape: [positionSection(), layoutSection(), fillSection(), shadowSection()],
}

function positionSection() {
  return {
    id: "position",
    title: "Position",
    fields: [
      { key: "x", label: "X", kind: "number", unit: "px" },
      { key: "y", label: "Y", kind: "number", unit: "px" },
    ],
  } satisfies InspectorSchema<PosterItem>["frame"][number]
}

function layoutSection() {
  return {
    id: "layout",
    title: "Layout",
    fields: [
      { key: "w", label: "W", kind: "number", unit: "px", min: 0 },
      { key: "h", label: "H", kind: "number", unit: "px", min: 0 },
    ],
  } satisfies InspectorSchema<PosterItem>["frame"][number]
}

function fillSection() {
  return {
    id: "fill",
    title: "Fill",
    fields: [
      {
        key: "fill",
        label: "Color",
        kind: "popover",
        renderEditor: (value, set) => (
          <div
            role="group"
            aria-label="Fill color"
            className="grid grid-cols-3 gap-1.5"
          >
            {FILLS.map((fill) => (
              <button
                key={fill.value}
                type="button"
                aria-pressed={value === fill.value}
                onClick={() => set(fill.value)}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-md p-1.5 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
                  value === fill.value && "bg-muted font-medium"
                )}
              >
                <span
                  aria-hidden
                  className="size-8 rounded-md border"
                  style={{ background: `var(--${fill.value})` }}
                />
                {fill.label}
              </button>
            ))}
          </div>
        ),
      },
    ],
  } satisfies InspectorSchema<PosterItem>["frame"][number]
}

function shadowSection() {
  return {
    id: "shadow",
    title: "Shadow",
    optional: true,
    fields: [
      { key: "shadow", label: "Drop shadow", kind: "toggle" },
      {
        key: "blur",
        label: "Blur",
        kind: "number",
        unit: "px",
        min: 0,
        max: 40,
      },
    ],
  } satisfies InspectorSchema<PosterItem>["frame"][number]
}

const PREVIEW_ERROR = new Error(
  "Preview only: the inspector-demo collection could not be read."
)

type Preview = "live" | "empty" | "loading" | "error"
const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]

function Canvas({
  items,
  selectedIds,
  hoverId,
  select,
  hover,
}: {
  items: PosterItem[]
  selectedIds: string[]
  hoverId: string | null
  select: (id: string, mode: "replace" | "toggle") => void
  hover: (id: string | null) => void
}) {
  return (
    <div className="relative h-[480px] w-[704px] p-4">
      {items.map((item) => {
        const isSelected = selectedIds.includes(item.id)
        const isHover = hoverId === item.id
        const left = 16 + item.x
        const top = 16 + item.y
        return (
          <div
            key={item.id}
            role="button"
            tabIndex={0}
            aria-label={`${item.title}, ${item.type}`}
            aria-pressed={isSelected}
            onClick={(event) =>
              select(
                item.id,
                event.metaKey || event.ctrlKey ? "toggle" : "replace"
              )
            }
            onKeyDown={(event) => {
              if (event.key === " ") {
                event.preventDefault()
                select(item.id, "replace")
              } else if (event.key === "Enter") {
                select(item.id, "replace")
              }
            }}
            onPointerEnter={() => hover(item.id)}
            onPointerLeave={() => hover(null)}
            style={{
              position: "absolute",
              left,
              top,
              width: item.w,
              height: item.h,
              background:
                item.type === "text"
                  ? "transparent"
                  : `var(--${item.fill ?? "muted"})`,
              boxShadow: item.shadow
                ? `0 ${(item.blur ?? 8) / 2}px ${item.blur ?? 8}px rgb(0 0 0 / 0.3)`
                : undefined,
              fontSize: item.fontSize,
              textAlign: item.align as "left" | "center" | "right" | undefined,
            }}
            className={cn(
              "cursor-default overflow-hidden leading-tight outline-none select-none",
              item.type === "frame" && "border",
              isHover && !isSelected && "outline outline-1 outline-primary/50",
              isSelected && "outline outline-2 outline-primary",
              "focus-visible:ring-2 focus-visible:ring-ring"
            )}
          >
            {item.type === "text" ? item.text : null}
            {isSelected ? (
              <span className="pointer-events-none absolute right-0 bottom-0 rounded-tl bg-primary px-1 text-[10px] leading-4 text-primary-foreground">
                {item.w} x {item.h}
              </span>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

function PageView({ items }: { items: PosterItem[] }) {
  const count = (type: PosterItem["type"]) =>
    items.filter((item) => item.type === type).length
  return (
    <div className="flex flex-col gap-3">
      <dl className="grid grid-cols-3 gap-1.5 text-center text-xs">
        {(["frame", "text", "shape"] as const).map((type) => (
          <div key={type} className="rounded-md bg-muted p-2">
            <dt className="text-muted-foreground capitalize">{type}s</dt>
            <dd className="text-sm font-semibold">{count(type)}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-muted-foreground">
        Select a layer in the tree or on the canvas to edit it. Use Shift or
        Ctrl click to select several.
      </p>
    </div>
  )
}

export default function Demo() {
  const collection = useCollection<PosterItem>("inspector-demo", seed)
  const [preview, setPreview] = useState<Preview>("live")

  const status =
    preview === "loading" || preview === "error" ? preview : collection.status
  const items = preview === "empty" ? [] : collection.items

  const addFrame = async () => {
    await collection.add(
      frame(crypto.randomUUID(), "New frame", null, 0, 0, 200, 120, "card")
    )
    setPreview("live")
  }

  return (
    <div className="flex h-full min-h-[34rem] flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b px-3 py-1.5">
        <span
          id="inspector-demo-preview"
          className="text-xs text-muted-foreground"
        >
          Preview state
        </span>
        <div
          role="group"
          aria-labelledby="inspector-demo-preview"
          className="flex gap-1"
        >
          {PREVIEWS.map((option) => (
            <Button
              key={option}
              size="xs"
              variant={preview === option ? "secondary" : "outline"}
              aria-pressed={preview === option}
              onClick={() => setPreview(option)}
              className="capitalize"
            >
              {option}
            </Button>
          ))}
        </div>
        <Button
          size="xs"
          variant="ghost"
          className="ml-auto"
          onClick={() => {
            setPreview("live")
            void collection.replaceAll(seed)
          }}
        >
          Reset sample data
        </Button>
      </div>
      <div className="min-h-0 flex-1">
        <Inspector
          items={items}
          schema={schema}
          status={status}
          error={preview === "error" ? PREVIEW_ERROR : collection.error}
          onRetry={() => setPreview("live")}
          onUpdate={async (ids, patch) => {
            await Promise.all(ids.map((id) => collection.update(id, patch)))
          }}
          onRemove={async (ids) => {
            await Promise.all(ids.map((id) => collection.remove(id)))
          }}
          onRename={(id, title) => collection.update(id, { title })}
          renderCanvas={(ctx) => <Canvas {...ctx} />}
          pageView={<PageView items={items} />}
          emptyView={
            <EmptyState
              title="No layers yet"
              description="Add a frame to start laying out a poster."
              action={
                <Button size="sm" onClick={() => void addFrame()}>
                  Add frame
                </Button>
              }
            />
          }
        />
      </div>
    </div>
  )
}
