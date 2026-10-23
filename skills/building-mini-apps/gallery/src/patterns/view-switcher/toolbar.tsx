import type { Ref } from "react"
import {
  ArrowUpDownIcon,
  ListFilterIcon,
  PlusIcon,
  SearchIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Kbd } from "@/components/ui/kbd"
import {
  Popover,
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import { defaultRule, pickField, type Field } from "./fields"
import { RuleEditor } from "./rule-editor"
import type { SortRule, ViewConfig } from "./types"

const NO_SORT = "__none__"

function ToolbarButton({
  label,
  shortcut,
  active,
  disabled,
  icon,
}: {
  label: string
  shortcut: string
  active: boolean
  disabled: boolean
  icon: React.ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="icon-sm"
            disabled={disabled}
            aria-label={active ? `${label} (on)` : label}
            className={cn(active && "text-(--mini-accent)")}
          >
            {icon}
          </Button>
        </PopoverTrigger>
      </TooltipTrigger>
      <TooltipContent>
        {label} <Kbd>{shortcut}</Kbd>
      </TooltipContent>
    </Tooltip>
  )
}

function FilterPopover({
  view,
  fields,
  open,
  disabled,
  onOpenChange,
  onChange,
}: {
  view: ViewConfig
  fields: Field[]
  open: boolean
  disabled: boolean
  onOpenChange(open: boolean): void
  onChange(filters: ViewConfig["filters"]): void
}) {
  const rules = view.filters
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <ToolbarButton
        label="Filter"
        shortcut="F"
        active={rules.length > 0}
        disabled={disabled}
        icon={<ListFilterIcon />}
      />
      <PopoverContent align="end" className="w-80">
        <p className="text-xs font-medium">Filter</p>
        {rules.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No filters. Every record is shown.
          </p>
        ) : null}
        {rules.map((rule, index) => (
          <RuleEditor
            key={index}
            rule={rule}
            fields={fields}
            onChange={(next) =>
              onChange(rules.map((r, i) => (i === index ? next : r)))
            }
            onRemove={() => onChange(rules.filter((_, i) => i !== index))}
          />
        ))}
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            size="xs"
            onClick={() => onChange([...rules, defaultRule(fields[0])])}
          >
            <PlusIcon />
            Add filter
          </Button>
          {rules.length > 0 ? (
            <Button variant="ghost" size="xs" onClick={() => onChange([])}>
              Clear all
            </Button>
          ) : null}
        </div>
      </PopoverContent>
    </Popover>
  )
}

function SortPopover({
  view,
  fields,
  open,
  disabled,
  onOpenChange,
  onChange,
}: {
  view: ViewConfig
  fields: Field[]
  open: boolean
  disabled: boolean
  onOpenChange(open: boolean): void
  onChange(sort: SortRule | undefined): void
}) {
  const sort = view.sort
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <ToolbarButton
        label="Sort"
        shortcut="S"
        active={Boolean(sort)}
        disabled={disabled}
        icon={<ArrowUpDownIcon />}
      />
      <PopoverContent align="end" className="w-64">
        <p className="text-xs font-medium">Sort</p>
        <Select
          value={sort?.field ?? NO_SORT}
          onValueChange={(field) =>
            onChange(
              field === NO_SORT ? undefined : { field, dir: sort?.dir ?? "asc" }
            )
          }
        >
          <SelectTrigger size="sm" className="w-full" aria-label="Sort by">
            <SelectValue />
          </SelectTrigger>
          <SelectContent position="popper">
            <SelectItem value={NO_SORT}>No sorting</SelectItem>
            {fields.map((f) => (
              <SelectItem key={f.key} value={f.key}>
                {f.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {sort ? (
          <Select
            value={sort.dir}
            onValueChange={(dir) =>
              onChange({ ...sort, dir: dir === "desc" ? "desc" : "asc" })
            }
          >
            <SelectTrigger
              size="sm"
              className="w-full"
              aria-label="Sort direction"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper">
              <SelectItem value="asc">Ascending</SelectItem>
              <SelectItem value="desc">Descending</SelectItem>
            </SelectContent>
          </Select>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}

function LayoutSetting({
  view,
  fields,
  disabled,
  onChange,
}: {
  view: ViewConfig
  fields: Field[]
  disabled: boolean
  onChange(patch: Partial<ViewConfig>): void
}) {
  if (view.layout !== "board" && view.layout !== "calendar") return null
  const board = view.layout === "board"
  const type = board ? "select" : "date"
  const choices = fields.filter((f) => f.type === type)
  if (choices.length === 0) return null
  const current = pickField(fields, board ? view.groupBy : view.dateField, type)
  const label = board ? "Group by" : "Date field"
  return (
    <Select
      value={current?.key}
      disabled={disabled}
      onValueChange={(key) =>
        onChange(board ? { groupBy: key } : { dateField: key })
      }
    >
      <SelectTrigger
        size="sm"
        aria-label={label}
        className="h-7 gap-1 border-transparent text-xs"
      >
        <span className="text-muted-foreground">{label}</span>
        <SelectValue />
      </SelectTrigger>
      <SelectContent position="popper" align="end">
        {choices.map((f) => (
          <SelectItem key={f.key} value={f.key}>
            {f.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export interface ToolbarProps {
  view: ViewConfig
  /** Every field including the title. */
  fields: Field[]
  disabled: boolean
  showSearch: boolean
  query: string
  searchRef: Ref<HTMLInputElement>
  filterOpen: boolean
  sortOpen: boolean
  onQueryChange(query: string): void
  onFilterOpenChange(open: boolean): void
  onSortOpenChange(open: boolean): void
  onViewChange(patch: Partial<ViewConfig>): void
}

export function Toolbar(props: ToolbarProps) {
  const {
    view,
    fields,
    disabled,
    showSearch,
    query,
    searchRef,
    filterOpen,
    sortOpen,
    onQueryChange,
    onFilterOpenChange,
    onSortOpenChange,
    onViewChange,
  } = props
  return (
    <div className="flex shrink-0 items-center gap-1">
      {showSearch ? (
        <div className="relative">
          <SearchIcon
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            ref={searchRef}
            type="search"
            value={query}
            disabled={disabled}
            placeholder="Search"
            aria-label="Search"
            title="Search (/)"
            className="h-7 w-36 pl-7 text-xs"
            onChange={(e) => onQueryChange(e.target.value)}
          />
        </div>
      ) : null}
      <FilterPopover
        view={view}
        fields={fields}
        open={filterOpen}
        disabled={disabled}
        onOpenChange={onFilterOpenChange}
        onChange={(filters) => onViewChange({ filters })}
      />
      <SortPopover
        view={view}
        fields={fields}
        open={sortOpen}
        disabled={disabled}
        onOpenChange={onSortOpenChange}
        onChange={(sort) => onViewChange({ sort })}
      />
      <LayoutSetting
        view={view}
        fields={fields}
        disabled={disabled}
        onChange={onViewChange}
      />
    </div>
  )
}
