import { useEffect, useRef, useState, type ReactNode } from "react"
import {
  CalendarDaysIcon,
  Columns3Icon,
  CopyIcon,
  EllipsisIcon,
  ListIcon,
  PencilIcon,
  PlusIcon,
  Table2Icon,
  Trash2Icon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import { ConfirmDialog } from "./confirm-dialog"
import { pickField, type Field } from "./fields"
import type { Layout, ViewConfig } from "./types"

const LAYOUTS: {
  layout: Layout
  label: string
  icon: ReactNode
  needs?: "select" | "date"
}[] = [
  { layout: "table", label: "Table", icon: <Table2Icon /> },
  { layout: "board", label: "Board", icon: <Columns3Icon />, needs: "select" },
  { layout: "list", label: "List", icon: <ListIcon /> },
  {
    layout: "calendar",
    label: "Calendar",
    icon: <CalendarDaysIcon />,
    needs: "date",
  },
]

export function layoutIcon(layout: Layout): ReactNode {
  return LAYOUTS.find((l) => l.layout === layout)?.icon
}

function LayoutTile({
  label,
  icon,
  disabledReason,
  onPick,
}: {
  label: string
  icon: ReactNode
  disabledReason?: string
  onPick(): void
}) {
  const button = (
    <Button
      variant="outline"
      className="h-14 w-full flex-col gap-1 text-xs"
      disabled={Boolean(disabledReason)}
      onClick={onPick}
    >
      {icon}
      {label}
    </Button>
  )
  if (!disabledReason) return button
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className="block rounded-lg outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {button}
        </span>
      </TooltipTrigger>
      <TooltipContent>{disabledReason}</TooltipContent>
    </Tooltip>
  )
}

function AddViewButton({
  fields,
  disabled,
  onAdd,
}: {
  fields: Field[]
  disabled: boolean
  onAdd(layout: Layout): void
}) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              disabled={disabled}
              aria-label="Add a new view"
            >
              <PlusIcon />
            </Button>
          </PopoverTrigger>
        </TooltipTrigger>
        <TooltipContent>Add a new view</TooltipContent>
      </Tooltip>
      <PopoverContent align="start" className="w-60">
        <p className="text-xs font-medium">New view</p>
        <div className="grid grid-cols-2 gap-2">
          {LAYOUTS.map(({ layout, label, icon, needs }) => (
            <LayoutTile
              key={layout}
              label={label}
              icon={icon}
              disabledReason={
                needs && !pickField(fields, undefined, needs)
                  ? `Needs a ${needs} field, and there isn't one`
                  : undefined
              }
              onPick={() => {
                setOpen(false)
                onAdd(layout)
              }}
            />
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}

export interface TabStripProps {
  views: ViewConfig[]
  activeId: string
  disabled: boolean
  /** Every field including the title. */
  fields: Field[]
  onSelect(id: string): void
  onAdd(layout: Layout): Promise<boolean>
  onRename(id: string, name: string): void
  onDuplicate(id: string): Promise<boolean>
  onDelete(id: string): void
}

/** Named view tabs with a "+" layout picker and a menu for the active tab. */
export function TabStrip(props: TabStripProps) {
  const { views, activeId, disabled, fields, onSelect } = props
  const active = views.find((v) => v.id === activeId) ?? views[0]
  const [renaming, setRenaming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const menuSettled = useRef(true)
  const renameWanted = useRef(false)
  const listRef = useRef<HTMLDivElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    listRef.current
      ?.querySelector('[role="tab"][data-state="active"]')
      ?.scrollIntoView({ inline: "nearest", block: "nearest" })
  }, [activeId, views.length])

  // opening the name field while the menu is still unmounting makes the popover dismiss itself
  function requestRename() {
    if (menuSettled.current) setRenaming(true)
    else renameWanted.current = true
  }

  async function created(work: Promise<boolean>) {
    if (await work) requestRename()
  }

  return (
    <div className="flex min-w-0 items-center gap-1">
      <div ref={listRef} className="hidden min-w-0 overflow-x-auto sm:block">
        <TabsList className="h-8 w-max gap-0.5 bg-transparent p-0">
          {views.map((view) => (
            <TabsTrigger
              key={view.id}
              value={view.id}
              disabled={disabled}
              className={cn(
                "h-7 flex-none gap-1.5 px-2 text-xs",
                "data-[state=active]:bg-secondary data-[state=active]:text-foreground data-[state=active]:shadow-none dark:data-[state=active]:border-transparent dark:data-[state=active]:bg-secondary"
              )}
            >
              {layoutIcon(view.layout)}
              {view.name}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      <Select value={active.id} onValueChange={onSelect} disabled={disabled}>
        <SelectTrigger
          size="sm"
          aria-label="View"
          className="min-w-0 sm:hidden"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent position="popper">
          {views.map((view) => (
            <SelectItem key={view.id} value={view.id}>
              {view.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Popover open={renaming} onOpenChange={setRenaming}>
        <PopoverAnchor asChild>
          <div className="shrink-0">
            <DropdownMenu
              onOpenChange={(open) => {
                if (!open) menuSettled.current = false
              }}
            >
              <DropdownMenuTrigger asChild>
                <Button
                  ref={menuButtonRef}
                  variant="ghost"
                  size="icon-sm"
                  disabled={disabled}
                  aria-label={`Options for view ${active.name}`}
                >
                  <EllipsisIcon />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                onCloseAutoFocus={(e) => {
                  menuSettled.current = true
                  if (!renameWanted.current) return
                  e.preventDefault()
                  renameWanted.current = false
                  setRenaming(true)
                }}
              >
                <DropdownMenuItem
                  onSelect={() => {
                    menuSettled.current = false
                    requestRename()
                  }}
                >
                  <PencilIcon />
                  Rename
                </DropdownMenuItem>
                <DropdownMenuItem
                  onSelect={() => {
                    menuSettled.current = false
                    void created(props.onDuplicate(active.id))
                  }}
                >
                  <CopyIcon />
                  Duplicate
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  disabled={views.length <= 1}
                  onSelect={() => setDeleting(true)}
                >
                  <Trash2Icon />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </PopoverAnchor>
        <PopoverContent
          align="start"
          className="w-60"
          aria-label="Rename view"
          onCloseAutoFocus={(e) => {
            e.preventDefault()
            menuButtonRef.current?.focus()
          }}
        >
          <form
            className="flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              const name = new FormData(e.currentTarget).get("name")
              if (typeof name === "string" && name.trim())
                props.onRename(active.id, name.trim())
              setRenaming(false)
            }}
          >
            <label htmlFor="view-name" className="text-xs font-medium">
              View name
            </label>
            <Input
              id="view-name"
              name="name"
              defaultValue={active.name}
              className="h-7 text-xs"
              onFocus={(e) => e.target.select()}
            />
            <Button type="submit" size="sm">
              Save
            </Button>
          </form>
        </PopoverContent>
      </Popover>

      <AddViewButton
        fields={fields}
        disabled={disabled}
        onAdd={(layout) => void created(props.onAdd(layout))}
      />

      <ConfirmDialog
        open={deleting}
        title={`Delete view "${active.name}"?`}
        description="The records stay; only this saved view, with its filters and sort, is removed."
        confirmLabel="Delete view"
        returnFocusRef={menuButtonRef}
        onOpenChange={setDeleting}
        onConfirm={() => props.onDelete(active.id)}
      />
    </div>
  )
}
