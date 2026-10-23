import { useId } from "react"
import { EllipsisIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

import { IndeterminateCheckbox } from "./indeterminate-checkbox"
import { CHECKBOX_COLUMN, type BulkSelectAction } from "./types"
import type { SelectionState } from "./selection"

function BarButton({
  action,
  run,
}: {
  action: BulkSelectAction
  run: () => void
}) {
  const reasonId = useId()
  const reason = action.disabledReason
  const button = (
    <Button
      size="sm"
      variant="outline"
      aria-disabled={reason ? true : undefined}
      aria-describedby={reason ? reasonId : undefined}
      className="aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
      onClick={() => {
        if (!reason) run()
      }}
    >
      {action.icon}
      {action.label}
    </Button>
  )
  if (!reason) return button
  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent>{reason}</TooltipContent>
      </Tooltip>
      <span id={reasonId} className="sr-only">
        {reason}
      </span>
    </>
  )
}

/**
 * The header band while rows are selected: the select-all box, the caller's
 * actions as buttons, an overflow menu for actions marked `overflow`, and the
 * count. A disabled action stays in place and gives its reason as a tooltip
 * (or a sub-line in the menu). Same height as the column header it replaces.
 */
export function ActionBar({
  actions,
  selectedIds,
  selectionState,
  noun,
  onToggleAll,
}: {
  actions: BulkSelectAction[]
  selectedIds: string[]
  selectionState: SelectionState
  noun: string
  onToggleAll: () => void
}) {
  const buttons = actions.filter((action) => !action.overflow)
  const menu = actions.filter((action) => action.overflow)
  const count = selectedIds.length
  return (
    <div
      role="toolbar"
      aria-label="Actions for the selected rows"
      className="flex h-10 items-center"
    >
      <div
        className="flex shrink-0 justify-center"
        style={{ width: CHECKBOX_COLUMN }}
      >
        <IndeterminateCheckbox
          checked={
            selectionState === "all"
              ? true
              : selectionState === "some"
                ? "mixed"
                : false
          }
          onToggle={onToggleAll}
          label="Select all rows"
        />
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-1.5 pr-3">
        {buttons.map((action) => (
          <BarButton
            key={action.id}
            action={action}
            run={() => action.onSelect(selectedIds)}
          />
        ))}
        {menu.length > 0 ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon-sm"
                variant="outline"
                aria-label="More actions"
              >
                <EllipsisIcon aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-52">
              {menu.map((action) => (
                <DropdownMenuItem
                  key={action.id}
                  disabled={Boolean(action.disabledReason)}
                  onSelect={() => action.onSelect(selectedIds)}
                >
                  {action.icon}
                  <span className="flex flex-col">
                    <span>{action.label}</span>
                    {action.disabledReason ? (
                      <span className="text-xs text-muted-foreground">
                        {action.disabledReason}
                      </span>
                    ) : null}
                  </span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
        <span className="ml-2 text-xs whitespace-nowrap text-muted-foreground tabular-nums">
          {count} {count === 1 ? noun : `${noun}s`} selected
        </span>
      </div>
    </div>
  )
}
