import { useMemo, useRef, useState } from "react"
import { ChevronDownIcon, UserIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

import {
  filterAssigneeGroups,
  findAssignee,
  initials,
  type AssigneeGroup,
} from "./assignees"

function Avatar({ name }: { name?: string }) {
  if (!name) {
    return (
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-dashed border-muted-foreground/60 text-muted-foreground">
        <UserIcon className="size-3.5" aria-hidden />
      </span>
    )
  }
  return (
    <span
      aria-hidden
      className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[var(--mini-accent-soft)] text-[10px] font-medium text-foreground"
    >
      {initials(name)}
    </span>
  )
}

/**
 * Avatar button that opens a popover to pick an assignee: a header with a
 * Clear link, an auto-focused search box, and the caller's groups. Choosing an
 * option or Clear calls `onChange` (with `null` for Clear) and closes it; Esc
 * closes it without changing anything.
 */
export function AssigneeCell({
  value,
  groups,
  onChange,
  label = "Assignee",
}: {
  value: string | null
  groups: AssigneeGroup[]
  onChange: (id: string | null) => void
  label?: string
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const searchRef = useRef<HTMLInputElement>(null)
  const current = findAssignee(groups, value)
  const shown = useMemo(
    () => filterAssigneeGroups(groups, query),
    [groups, query]
  )
  const name = current ? current.name : "unassigned"

  const choose = (id: string | null) => {
    onChange(id)
    setOpen(false)
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setQuery("")
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`${label}: ${name}. Change`}
          title={current ? `${label}: ${current.name}` : `${label}: unassigned`}
          className="flex items-center gap-0.5 rounded-full border border-border bg-background p-0.5 pr-1.5 outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-expanded:bg-muted"
        >
          <Avatar name={current?.name} />
          <ChevronDownIcon
            className="size-3 text-muted-foreground"
            aria-hidden
          />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-64 gap-0 p-0"
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          searchRef.current?.focus()
        }}
      >
        <div className="flex items-center justify-between px-3 pt-2.5 pb-1">
          <span className="text-xs font-medium">{label}</span>
          <Button
            variant="link"
            size="xs"
            disabled={value === null}
            onClick={() => choose(null)}
            className="h-auto p-0 text-xs"
          >
            Clear
          </Button>
        </div>
        <Command
          shouldFilter={false}
          className="rounded-none! bg-transparent p-0"
        >
          <CommandInput
            ref={searchRef}
            value={query}
            onValueChange={setQuery}
            placeholder="Search people or teams"
            aria-label={`Search ${label.toLowerCase()}`}
          />
          <CommandList>
            <CommandEmpty>No one matches.</CommandEmpty>
            {shown.map((group) => (
              <CommandGroup key={group.id} heading={group.label}>
                {group.options.map((option) => (
                  <CommandItem
                    key={option.id}
                    value={`${group.id}:${option.id}`}
                    data-checked={option.id === value}
                    onSelect={() => choose(option.id)}
                  >
                    <Avatar name={option.name} />
                    <span className="truncate">{option.name}</span>
                    {option.hint ? (
                      <span className="truncate text-xs text-muted-foreground">
                        {option.hint}
                      </span>
                    ) : null}
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
