import { useState } from "react"

import { Button } from "@/components/ui/button"
import { useCollection } from "@/lib/mini/store"

import { StackTrace } from "./stack-trace"
import type { SourceLine, StackException, StackFrame } from "./types"

type Failure = {
  id: string
  name: string
  summary: string
  exceptions: StackException[]
}

const PREVIEWS = ["live", "empty", "loading", "error"] as const
type Preview = (typeof PREVIEWS)[number]

const HINTS = [
  "Up and Down move between rows",
  "Home and End jump to the first and last",
  "Enter or Space opens or closes the focused row",
  "Most relevant folds library frames; Full shows them all",
  "The order button reverses the frames",
]

function source(start: number, text: string): SourceLine[] {
  return text
    .split("\n")
    .map((line, index) => ({ no: start + index, text: line }))
}

function library(
  prefix: string,
  file: string,
  functions: string[],
  module: string
): StackFrame[] {
  return functions.map((fn, index) => ({
    id: `${prefix}${index + 1}`,
    filename: file,
    module,
    function: fn,
    lineNo: 40 + index * 7,
    colNo: 9 + index,
    inApp: false,
  }))
}

const RUNNER_FUNCTIONS = [
  "startWorker",
  "loadSuite",
  "collectTests",
  "runSuite",
  "runSuiteBody",
  "runHooks",
  "beforeEachHooks",
  "runTest",
  "withTimeout",
  "withRetries",
  "invokeTest",
  "callUserFn",
  "applyFixtures",
  "resolveFixtures",
  "wrapAsync",
  "settle",
  "dispatch",
]

const TOTALS_SOURCE = source(
  67,
  `  const base = lines.reduce((sum, line) => sum + line.price * line.qty, 0)

  const label = "Applied " + cart.discount.name + " (" + cart.discount.code + ") to " + lines.length + " lines"
  let total = base
  if (cart.discount) {
    log.debug(label)
    total -= cart.discount.coupon.amount
  }

  return roundCents(total)
}
`.trimEnd()
)

const CHECKOUT_SOURCE = source(
  26,
  `export function checkout(cart: Cart): Receipt {
  const lines = priceLines(cart.items)
  const subtotal = sumLines(lines)

  const total = reduceLines(lines, (acc, line) =>
    applyCoupon({ ...cart, lines }, acc, line)
  )

  return { id: newReceiptId(), lines, subtotal, total }
}

export function priceLines(items: CartItem[]): Line[] {`
)

const SPEC_SOURCE = source(
  19,
  `describe("cart totals", () => {
  const cart = buildCart(["tea", "mug"])

  it("applies a coupon to a discounted cart", () => {
    cart.discount = { name: "Spring sale", code: "SPRING", coupon: undefined }
    const receipt = checkout(cart)

    expect(receipt.total).toBe(40)
  })

  it("keeps the subtotal when no coupon is given", () => {
    const receipt = checkout(buildCart(["tea"]))`
)

const SPEC_ASSERT_SOURCE = source(
  22,
  `  it("applies a coupon to a discounted cart", () => {
    cart.discount = { name: "Spring sale", code: "SPRING", coupon: undefined }
    const receipt = checkout(cart)

    expect(receipt.total).toBe(40)
  })

  it("keeps the subtotal when no coupon is given", () => {
    const receipt = checkout(buildCart(["tea"]))
    expect(receipt.total).toBe(receipt.subtotal)
  })`
)

const FORMAT_SOURCE = source(
  13,
  `export function formatDate(value: string | number): string {
  const when = new Date(value)

  // receipts keep the date the order was paid, not placed
  const paid = when.toISOString().slice(0, 10)
  const [year, month, day] = paid.split("-")

  return day + "/" + month + "/" + year
}

export function formatMoney(cents: number): string {
  return (cents / 100).toFixed(2)`
)

const LOAD_SOURCE = source(
  8,
  `export function loadConfig(path: string): Config {
  const text = readText(path)
  return parseConfig(text)
}`
)

const SEED: Failure[] = [
  {
    id: "coupon",
    name: "applies a coupon to a discounted cart",
    summary: "Two chained exceptions, one folded run of 17 frames and one of 3",
    exceptions: [
      {
        id: "coupon-type",
        type: "TypeError",
        value: "Cannot read properties of undefined (reading 'amount')",
        mechanism: "runtime",
        handled: false,
        frames: [
          ...library(
            "runner",
            "node_modules/mini-runner/dist/worker.js",
            RUNNER_FUNCTIONS,
            "mini-runner"
          ),
          {
            id: "spec",
            filename: "tests/cart.spec.ts",
            function: "applies a coupon to a discounted cart",
            lineNo: 24,
            colNo: 21,
            inApp: true,
            contextLines: SPEC_SOURCE,
          },
          {
            id: "run-checkout",
            filename: "src/cart/index.ts",
            function: "runCheckout",
            lineNo: 12,
            colNo: 10,
            inApp: true,
          },
          {
            id: "checkout",
            filename: "src/cart/checkout.ts",
            function: "checkout",
            lineNo: 30,
            colNo: 17,
            inApp: true,
            contextLines: CHECKOUT_SOURCE,
          },
          ...library(
            "iter",
            "node_modules/tiny-iter/lib/reduce.js",
            ["reduceLines", "step", "next"],
            "tiny-iter"
          ),
          {
            id: "totals",
            filename: "src/cart/totals.ts",
            function: "applyCoupon",
            lineNo: 73,
            colNo: 30,
            inApp: true,
            contextLines: TOTALS_SOURCE,
          },
        ],
      },
      {
        id: "coupon-assert",
        type: "AssertionError",
        value:
          "Expected the cart total to be 40, but the cart could not be priced",
        mechanism: "assertion",
        handled: true,
        frames: [
          ...library(
            "run2-",
            "node_modules/mini-runner/dist/worker.js",
            ["runTest", "invokeTest", "callUserFn", "settle"],
            "mini-runner"
          ),
          {
            id: "spec-assert",
            filename: "tests/cart.spec.ts",
            function: "applies a coupon to a discounted cart",
            lineNo: 26,
            colNo: 5,
            inApp: true,
            contextLines: SPEC_ASSERT_SOURCE,
          },
          ...library(
            "assert",
            "node_modules/tiny-assert/index.js",
            ["toBe", "fail"],
            "tiny-assert"
          ),
        ],
      },
    ],
  },
  {
    id: "receipt-date",
    name: "formats the paid date on a receipt",
    summary:
      "The failing frame is inside a library; one in-app caller above it",
    exceptions: [
      {
        id: "date-range",
        type: "RangeError",
        value: "Invalid time value",
        mechanism: "runtime",
        handled: false,
        frames: [
          ...library(
            "run3-",
            "node_modules/mini-runner/dist/worker.js",
            ["runTest", "invokeTest", "callUserFn", "settle", "dispatch"],
            "mini-runner"
          ),
          {
            id: "format",
            filename: "src/receipt/format.ts",
            function: "formatDate",
            lineNo: 17,
            colNo: 22,
            inApp: true,
            contextLines: FORMAT_SOURCE,
          },
          ...library(
            "dates",
            "node_modules/tiny-dates/lib/iso.js",
            ["toISOString"],
            "tiny-dates"
          ),
        ],
      },
    ],
  },
  {
    id: "config",
    name: "loads the config file",
    summary: "No in-app frames, so Most relevant shows every frame",
    exceptions: [
      {
        id: "config-missing",
        type: "Error",
        value: "ENOENT: no such file or directory, open 'config/app.json'",
        mechanism: "system",
        handled: false,
        frames: [
          ...library(
            "cfg",
            "node_modules/tiny-config/lib/load.js",
            ["parseConfig", "loadConfig"],
            "tiny-config"
          ),
          {
            id: "cfg-read",
            filename: "node_modules/tiny-config/lib/read.js",
            module: "tiny-config",
            function: "loadConfig",
            lineNo: 10,
            colNo: 14,
            inApp: false,
            contextLines: LOAD_SOURCE,
          },
          ...library("fs", "node:fs", ["readFileSync", "openSync"], "node:fs"),
        ],
      },
    ],
  },
]

export default function Demo() {
  const failures = useCollection<Failure>("stack-trace-demo", SEED)
  const [preview, setPreview] = useState<Preview>("live")
  const [pickedId, setPickedId] = useState("coupon")

  const picked =
    failures.items.find((failure) => failure.id === pickedId) ??
    failures.items[0]
  const status =
    preview === "live"
      ? failures.status
      : preview === "empty"
        ? "ready"
        : preview
  const exceptions = preview === "live" && picked ? picked.exceptions : []

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">
          State preview (demo only)
        </span>
        <div role="group" aria-label="State preview" className="flex gap-1">
          {PREVIEWS.map((name) => (
            <Button
              key={name}
              size="xs"
              variant={preview === name ? "default" : "outline"}
              aria-pressed={preview === name}
              onClick={() => setPreview(name)}
              className="capitalize"
            >
              {name}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">Failed test</span>
        <div
          role="group"
          aria-label="Failed test"
          className="flex flex-wrap gap-1"
        >
          {failures.items.map((failure) => (
            <Button
              key={failure.id}
              size="xs"
              variant={picked?.id === failure.id ? "secondary" : "outline"}
              aria-pressed={picked?.id === failure.id}
              onClick={() => {
                setPickedId(failure.id)
                setPreview("live")
              }}
            >
              {failure.name}
            </Button>
          ))}
        </div>
      </div>
      {picked && preview === "live" ? (
        <p className="text-xs text-muted-foreground">{picked.summary}</p>
      ) : null}

      <div className="min-h-[24rem] flex-1 overflow-y-auto rounded-lg border p-4">
        <StackTrace
          aria-label="Failure stack trace"
          exceptions={exceptions}
          status={status}
          error={new Error("Could not read the failure report (simulated).")}
          onRetry={() => setPreview("live")}
        />
      </div>

      <p className="text-xs text-muted-foreground">{HINTS.join(" · ")}</p>
    </div>
  )
}
