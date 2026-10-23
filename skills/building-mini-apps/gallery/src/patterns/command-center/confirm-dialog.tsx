import { useRef, useState, type ReactNode, type RefObject } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { stateText } from "./attention"
import { toggleVerb } from "./tile-shared"
import type { Tile } from "./types"

/** Centered confirmation before a sensitive tile changes state. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  returnFocusRef,
  onConfirm,
  onOpenChange,
}: {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  /** Where focus goes on close; the dialog has no trigger element to return it to. */
  returnFocusRef: RefObject<HTMLElement | null>
  onConfirm(): void
  onOpenChange(open: boolean): void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        onCloseAutoFocus={(e) => {
          e.preventDefault()
          returnFocusRef.current?.focus()
        }}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              onOpenChange(false)
              onConfirm()
            }}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * Routes a tile toggle through a confirmation when the tile is `sensitive` and
 * calls `onToggle` directly otherwise. Render `dialog` once next to the caller.
 */
export function useToggleConfirm(onToggle: (tile: Tile) => void): {
  request(tile: Tile, trigger?: HTMLElement | null): void
  dialog: ReactNode
} {
  const [pending, setPending] = useState<Tile | null>(null)
  const [open, setOpen] = useState(false)
  const returnFocusRef = useRef<HTMLElement | null>(null)

  const request = (tile: Tile, trigger?: HTMLElement | null) => {
    if (!tile.sensitive) {
      onToggle(tile)
      return
    }
    returnFocusRef.current = trigger ?? null
    setPending(tile)
    setOpen(true)
  }

  const verb = pending ? toggleVerb(pending) : ""

  const dialog = (
    <ConfirmDialog
      open={open}
      title={pending ? `${verb} ${pending.name}?` : ""}
      description={
        pending
          ? `${pending.name} is ${stateText(pending).toLowerCase()} now.`
          : ""
      }
      confirmLabel={verb}
      returnFocusRef={returnFocusRef}
      onConfirm={() => pending && onToggle(pending)}
      onOpenChange={setOpen}
    />
  )

  return { request, dialog }
}
