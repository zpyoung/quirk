import {
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { SearchIcon, XIcon } from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import { cn } from "@/lib/utils"

import {
  EMPTY_QUERY,
  draftText,
  parseDraft,
  parseQuery,
  replaceLastWord,
  serializeQuery,
  serializeText,
  serializeToken,
  typingWord,
} from "./query"
import { flatten, suggest, type Suggestion } from "./suggestions"
import { optionDomId, SuggestionPopover } from "./suggestion-popover"
import { TokenChip } from "./token-chip"
import type { Query, QueryKey } from "./types"
import { useQueryState } from "./use-query-state"

export type QueryTokensProps = {
  keys: QueryKey[]
  value?: Query
  defaultValue?: Query
  onChange?: (query: Query) => void
  onSubmit?: (query: Query) => void
  urlParam?: string
  recent?: string[]
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  resultCount?: number
  emptyTitle?: string
  emptyAction?: ReactNode
  placeholder?: string
  autoFocus?: boolean
  boxClassName?: string
  toolbar?: ReactNode
  "aria-label"?: string
  children?: ReactNode
}

/**
 * Search box whose `key:value` words become removable chips, with a popover of keys, values and
 * recent searches. Free words stay as plain text. The parsed query is reported through `onChange`
 * as `{ tokens, text }`; the block takes data as props and never reads the store. `/` focuses the
 * box when focus is on the page body or inside the block. Results go in `children`, and the block
 * shows its Loading, Error and no-results states there.
 */
export function QueryTokens({
  keys,
  value,
  defaultValue,
  onChange,
  onSubmit,
  urlParam,
  recent = [],
  status = "ready",
  error,
  onRetry,
  resultCount,
  emptyTitle = "Nothing here yet",
  emptyAction,
  placeholder = "Search, or filter with key:value",
  autoFocus = false,
  boxClassName,
  toolbar,
  "aria-label": ariaLabel = "Search",
  children,
}: QueryTokensProps) {
  const uid = useId()
  const listId = `${uid}-suggestions`
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const [query, setQuery] = useQueryState({ value, defaultValue, onChange, urlParam, keys })
  const [draft, setDraft] = useState(() => serializeText(query.text))
  const [syncedText, setSyncedText] = useState(query.text)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [selected, setSelected] = useState<number | null>(null)

  // a controlled query can drop the chip that was selected; a stale index would make Enter edit a missing chip
  if (selected !== null && selected >= query.tokens.length) setSelected(null)

  // an outside change to the text (saved view, URL, clear) replaces what the input shows
  if (query.text !== syncedText) {
    setSyncedText(query.text)
    setDraft(serializeText(query.text))
  }

  const keyNames = useMemo(() => keys.map((k) => k.key), [keys])
  const disabled = status !== "ready"
  const list = suggest({
    word: typingWord(draft),
    keys,
    recent,
    draftEmpty: draft.trim() === "",
  })
  const options = flatten(list)
  const showPopover = open && !disabled && (options.length > 0 || list.hint !== undefined)
  const expanded = showPopover && options.length > 0
  const activeIndex = active < options.length ? active : -1

  const focusInput = () => inputRef.current?.focus()

  const commit = (submit: boolean) => {
    const { tokens, rest } = parseDraft(draft, { keys: keyNames, final: true })
    const next: Query = { tokens: [...query.tokens, ...tokens], text: draftText(rest) }
    setDraft(serializeText(next.text))
    if (tokens.length > 0 || next.text !== query.text) setQuery(next)
    if (submit && (next.tokens.length > 0 || next.text)) onSubmit?.(next)
  }

  const typeInto = (next: string) => {
    setSelected(null)
    setActive(-1)
    setOpen(true)
    const { tokens, rest } = parseDraft(next, { keys: keyNames })
    if (tokens.length === 0) return setDraft(next)
    setDraft(rest)
    setQuery({ tokens: [...query.tokens, ...tokens], text: query.text })
  }

  const removeChip = (index: number) => {
    setSelected(null)
    setQuery({ ...query, tokens: query.tokens.filter((_, i) => i !== index) })
    focusInput()
  }

  const editChip = (index: number) => {
    const word = serializeToken(query.tokens[index])
    setSelected(null)
    setQuery({ ...query, tokens: query.tokens.filter((_, i) => i !== index) })
    setDraft(draft && !/\s$/.test(draft) ? `${draft} ${word}` : draft + word)
    setOpen(true)
    focusInput()
  }

  const clear = () => {
    setSelected(null)
    setDraft("")
    setQuery(EMPTY_QUERY)
    setOpen(true)
    focusInput()
  }

  const choose = (item: Suggestion) => {
    setActive(-1)
    if (item.kind === "key") {
      setDraft(replaceLastWord(draft, item.word))
    } else if (item.kind === "value") {
      typeInto(`${replaceLastWord(draft, item.word)} `)
    } else if (item.kind === "recent") {
      const next = parseQuery(item.query, { keys: keyNames })
      setDraft(serializeText(next.text))
      setQuery(next)
      setOpen(false)
      onSubmit?.(next)
    } else {
      commit(true)
      setOpen(false)
    }
    focusInput()
  }

  const onKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.nativeEvent.isComposing) return
    const input = event.currentTarget
    const lastChip = query.tokens.length - 1
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault()
        if (!open) setOpen(true)
        else if (options.length > 0) setActive(Math.min(options.length - 1, activeIndex + 1))
        break
      case "ArrowUp":
        event.preventDefault()
        if (options.length > 0) setActive(Math.max(-1, activeIndex - 1))
        break
      case "Enter":
        event.preventDefault()
        if (selected !== null) editChip(selected)
        else if (expanded && activeIndex >= 0) choose(options[activeIndex])
        else {
          commit(true)
          setOpen(false)
        }
        break
      case "Escape":
        if (selected !== null) {
          event.preventDefault()
          setSelected(null)
        } else if (showPopover) {
          event.preventDefault()
          setOpen(false)
        } else input.blur()
        break
      case "Backspace":
        if (draft === "" && lastChip >= 0) {
          event.preventDefault()
          if (selected === null) setSelected(lastChip)
          else removeChip(selected)
        }
        break
      case "Delete":
        if (selected !== null) {
          event.preventDefault()
          removeChip(selected)
        }
        break
      case "ArrowLeft":
        if (lastChip >= 0 && input.selectionStart === 0 && input.selectionEnd === 0) {
          event.preventDefault()
          setSelected(selected === null ? lastChip : Math.max(0, selected - 1))
        }
        break
      case "ArrowRight":
        if (selected !== null) {
          event.preventDefault()
          setSelected(selected < lastChip ? selected + 1 : null)
        }
        break
    }
  }

  useHotkeys(
    "slash",
    (event) => {
      const target = event.target
      const inScope =
        target === document.body ||
        target === document.documentElement ||
        (target instanceof Node && rootRef.current?.contains(target) === true)
      if (!inScope) return
      event.preventDefault()
      focusInput()
    },
    { enabled: !disabled }
  )

  const searching = query.tokens.length > 0 || query.text !== ""
  let results: ReactNode = children
  if (status === "loading") results = <LoadingState label="Loading results" />
  else if (status === "error") {
    results = <ErrorState error={error ?? new Error("Could not load the results.")} onRetry={onRetry} />
  } else if (resultCount === 0) {
    results = searching ? (
      <EmptyState
        title="No results match this search"
        description={`Nothing matches ${serializeQuery(query)}. Edit the search or clear it.`}
        action={
          <Button size="sm" variant="outline" onClick={clear}>
            Clear search
          </Button>
        }
      />
    ) : (
      <EmptyState title={emptyTitle} action={emptyAction} />
    )
  }

  const selectedToken = selected !== null ? query.tokens[selected] : undefined

  return (
    <div ref={rootRef} className="flex min-h-0 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className={cn("relative min-w-0 grow basis-72", boxClassName)}>
          <div
            role="search"
            aria-label={ariaLabel}
            onMouseDown={(event) => {
              if (disabled || (event.target as Element).closest("input")) return
              event.preventDefault()
              focusInput()
            }}
            className={cn(
              "group flex min-h-9 w-full flex-wrap items-center gap-1.5 rounded-lg border border-input bg-background px-2.5 py-1 text-sm transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50",
              disabled && "opacity-60"
            )}
          >
            <SearchIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            {query.tokens.map((token, index) => (
              <TokenChip
                key={`${index}:${serializeToken(token)}`}
                token={token}
                selected={selected === index}
                disabled={disabled}
                onRemove={() => removeChip(index)}
                onEdit={() => editChip(index)}
              />
            ))}
            <input
              ref={inputRef}
              type="text"
              role="combobox"
              aria-label={ariaLabel}
              aria-autocomplete="list"
              aria-haspopup="listbox"
              aria-expanded={expanded}
              aria-controls={expanded ? listId : undefined}
              aria-activedescendant={expanded && activeIndex >= 0 ? optionDomId(listId, activeIndex) : undefined}
              autoComplete="off"
              spellCheck={false}
              autoFocus={autoFocus}
              disabled={disabled}
              value={draft}
              placeholder={query.tokens.length > 0 ? "" : disabled ? "Loading…" : placeholder}
              onChange={(event) => typeInto(event.target.value)}
              onKeyDown={onKeyDown}
              onFocus={() => setOpen(true)}
              onBlur={() => {
                setOpen(false)
                setSelected(null)
                if (draft !== serializeText(query.text)) commit(false)
              }}
              className="min-w-24 flex-1 bg-transparent py-0.5 outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
            />
            {searching || draft ? (
              <button
                type="button"
                aria-label="Clear search"
                disabled={disabled}
                onClick={clear}
                className="inline-flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60"
              >
                <XIcon className="size-3.5" aria-hidden />
              </button>
            ) : (
              <Kbd className="group-focus-within:hidden" aria-hidden>
                /
              </Kbd>
            )}
          </div>
          {showPopover ? (
            <SuggestionPopover
              listId={listId}
              sections={list.sections}
              hint={list.hint}
              activeIndex={activeIndex}
              onActivate={setActive}
              onChoose={choose}
            />
          ) : null}
          <span role="status" className="sr-only">
            {selectedToken
              ? `${selectedToken.key} ${selectedToken.value} selected. Press Backspace to remove or Enter to edit.`
              : ""}
          </span>
        </div>
        {toolbar}
      </div>
      {results ? <div className="min-h-0 flex-1">{results}</div> : null}
    </div>
  )
}
