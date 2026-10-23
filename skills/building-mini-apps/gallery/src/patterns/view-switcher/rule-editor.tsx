import { XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { OPS_BY_TYPE, OP_LABEL, defaultRule, type Field } from "./fields"
import type { FilterOp, FilterRule } from "./types"

function ValueEditor({
  field,
  rule,
  onChange,
}: {
  field: Field
  rule: FilterRule
  onChange(value: string | string[]): void
}) {
  const options = field.options ?? []
  if (field.type === "select" && rule.op === "anyOf") {
    const chosen = Array.isArray(rule.value)
      ? rule.value
      : rule.value
        ? [rule.value]
        : []
    return (
      <div
        role="group"
        aria-label={`${field.label} values`}
        className="flex flex-col gap-1"
      >
        {options.map((option) => (
          <label key={option} className="flex items-center gap-2 text-xs">
            <Checkbox
              checked={chosen.includes(option)}
              onCheckedChange={(on) =>
                onChange(
                  on === true
                    ? [...chosen, option]
                    : chosen.filter((v) => v !== option)
                )
              }
            />
            {option}
          </label>
        ))}
      </div>
    )
  }
  const single = Array.isArray(rule.value) ? (rule.value[0] ?? "") : rule.value
  if (field.type === "select") {
    return (
      <Select value={single} onValueChange={onChange}>
        <SelectTrigger
          size="sm"
          className="w-full"
          aria-label={`${field.label} value`}
        >
          <SelectValue placeholder="Choose..." />
        </SelectTrigger>
        <SelectContent position="popper">
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }
  const type =
    field.type === "date" ? "date" : field.type === "number" ? "number" : "text"
  return (
    <Input
      type={type}
      value={single}
      aria-label={`${field.label} value`}
      className="h-7 text-xs"
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

/** One filter rule as editable controls; every change is applied at once. */
export function RuleEditor({
  rule,
  fields,
  onChange,
  onRemove,
}: {
  rule: FilterRule
  fields: Field[]
  onChange(rule: FilterRule): void
  onRemove(): void
}) {
  const field = fields.find((f) => f.key === rule.field) ?? fields[0]

  function changeField(key: string) {
    const next = fields.find((f) => f.key === key)
    if (next) onChange(defaultRule(next))
  }

  function changeOp(op: FilterOp) {
    const wasMulti = rule.op === "anyOf"
    const multi = op === "anyOf"
    const value = wasMulti === multi ? rule.value : multi ? [] : ""
    onChange({ ...rule, op, value })
  }

  return (
    <div className="grid gap-1.5 rounded-md border p-2">
      <div className="flex items-center gap-1.5">
        <Select value={field.key} onValueChange={changeField}>
          <SelectTrigger
            size="sm"
            className="min-w-0 flex-1"
            aria-label="Filter field"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent position="popper">
            {fields.map((f) => (
              <SelectItem key={f.key} value={f.key}>
                {f.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={rule.op}
          onValueChange={(op) => changeOp(op as FilterOp)}
        >
          <SelectTrigger
            size="sm"
            className="min-w-0 flex-1"
            aria-label="Filter condition"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent position="popper">
            {OPS_BY_TYPE[field.type].map((op) => (
              <SelectItem key={op} value={op}>
                {OP_LABEL[op]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`Remove ${field.label} filter`}
          onClick={onRemove}
        >
          <XIcon />
        </Button>
      </div>
      <ValueEditor
        field={field}
        rule={rule}
        onChange={(value) => onChange({ ...rule, value })}
      />
    </div>
  )
}
