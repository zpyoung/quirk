import type { CSSProperties } from "react"

import { cn } from "@/lib/utils"

import { excerptWindow } from "./frames"
import type { SourceLine } from "./types"

const HANGING = 2

/** Leading spaces become padding so a wrapped line continues under the code, indented a little further. */
function lineStyle(text: string): CSSProperties {
  const indent = text.length - text.trimStart().length
  return { paddingLeft: `${indent + HANGING}ch`, textIndent: `-${HANGING}ch` }
}

/**
 * Numbered source lines with the failing line banded and marked. The mark is
 * a left bar plus hidden text, so it does not rely on color.
 */
export function CodeExcerpt({
  lines,
  failingLine,
  label,
}: {
  lines: readonly SourceLine[]
  failingLine?: number
  label: string
}) {
  const shown = excerptWindow(lines, failingLine)
  return (
    <div className="overflow-x-auto border-t border-border bg-background">
      <table
        aria-label={label}
        className="w-full border-collapse font-mono text-xs leading-[19px]"
      >
        <tbody>
          {shown.map((line) => {
            const failing = line.no === failingLine
            return (
              <tr
                key={line.no}
                data-failing={failing || undefined}
                className={cn(failing && "bg-[var(--mini-removed)]")}
              >
                <th
                  scope="row"
                  className={cn(
                    "w-12 min-w-12 border-l-2 px-2 text-right align-top font-normal text-muted-foreground tabular-nums select-none",
                    failing
                      ? "border-destructive text-foreground"
                      : "border-transparent"
                  )}
                >
                  {line.no}
                  {failing ? (
                    <span className="sr-only"> failing line</span>
                  ) : null}
                </th>
                <td className="w-full pr-3 align-top">
                  <span
                    className="block break-words whitespace-pre-wrap"
                    style={lineStyle(line.text)}
                  >
                    {line.text.trimStart() || " "}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
