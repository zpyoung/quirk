import { useMemo, useState, type ComponentProps, type DragEvent, type ReactNode } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { Heading } from '@astryxdesign/core/Heading'
import { Icon } from '@astryxdesign/core/Icon'
import { IconButton } from '@astryxdesign/core/IconButton'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { Link } from '@astryxdesign/core/Link'
import { Table, TableCell, pixel, proportional, type TableColumn, type TablePlugin } from '@astryxdesign/core/Table'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import type { LogicSpec, Placement, Requirement, RequirementGroup, ReviewState, ScopeCondition } from '../spec-types'
import {
  CONDITION_LABEL,
  GROUPS,
  GROUP_LABEL,
  effectiveCondition,
  effectivePlacement,
  placedRequirements,
  placementInSpec,
  requirementMoved,
  scopeWarnings,
} from '../review-state'
import type { ViewProps } from './view-props'
import { ChangedToken, CertaintyToken, GROUP_COLOR, ProvenanceToken } from './shared'
import { CONDITIONS, isAwaitingCall, setPlacement } from './board-model'
import { CallQueue } from './call-queue'
import { RequirementDialog } from './requirement-dialog'
import { useScopeOutGuard } from './scope-out-guard'

type TokenColor = ComponentProps<typeof Token>['color']
type Section = Placement
/** Where a dropped row lands: unconditionally in, out, or under one condition. */
type DropTarget = 'in' | 'out' | ScopeCondition
type Group = RequirementGroup | ScopeCondition
type BoardRow =
  | { kind: 'section'; id: string; section: Section; count: number }
  | { kind: 'group'; id: string; group: Group; count: number }
  | { kind: 'item'; id: string; requirement: Requirement; target: DropTarget }

const isCondition = (value: string): value is ScopeCondition => (CONDITIONS as string[]).includes(value)
const SECTION_LABEL: Record<Section, string> = { in: 'In scope', conditional: 'Conditionally in scope', out: 'Out of scope' }
const SECTION_HINT: Record<Section, string> = {
  in: 'The spec: the minimum first, then the rest from most to least impact.',
  conditional: 'Built only if it fits its code budget; dropped otherwise.',
  out: 'Deliberately not built.',
}
const HEADER_COLOR = {
  'section-in': 'green',
  'section-conditional': 'pink',
  'section-out': 'gray',
  'group-min': 'blue',
  'group-i3': 'orange',
  'group-i2': 'yellow',
  'group-i1': 'cyan',
  'group-no-code': 'default',
  'group-under-10': 'default',
  'group-under-30': 'default',
} as const
const GROUP_HINT: Record<Group, string> = {
  min: 'The absolute minimum for the first increment.',
  i3: 'Highest impact: getting this wrong breaks core behavior or leaves a whole area unhandled.',
  i2: 'Medium impact: getting this wrong shows up only in specific situations.',
  i1: 'Lowest impact: cosmetic, or a narrow edge case.',
  'no-code': 'Dropped if it needs any new code.',
  'under-10': 'Dropped if it needs 10 or more lines of new code.',
  'under-30': 'Dropped if it needs 30 or more lines of new code.',
}
const groupLabel = (group: Group) => (isCondition(group) ? CONDITION_LABEL[group] : GROUP_LABEL[group])

/** The drop target a placed requirement currently occupies: its condition when conditional, else its placement. */
function targetOf(state: ReviewState, requirement: Requirement): DropTarget {
  const placement = effectivePlacement(state, requirement)
  if (placement === 'conditional') return effectiveCondition(state, requirement)
  return placement === 'out' ? 'out' : 'in'
}

function Tag({ label, color }: { label: string; color?: TokenColor }) {
  return <Token size="sm" color={color} label={label} />
}

function RowTags({ requirement, state, changedIds, warningCount }: { requirement: Requirement; state: ReviewState; changedIds: Set<string>; warningCount: number }) {
  if (isAwaitingCall(state, requirement)) return null
  const placement = effectivePlacement(state, requirement)
  const needsReason = requirementMoved(state, requirement) && !state.moveReasons[requirement.id]?.trim()
  return (
    <HStack gap={1} wrap="wrap">
      <ProvenanceToken requirement={requirement} />
      <CertaintyToken certainty={requirement.certainty} />
      {placement === 'conditional' ? <Tag color={GROUP_COLOR[requirement.group]} label={`Claude's group: ${GROUP_LABEL[requirement.group]}`} /> : null}
      {needsReason ? <Tag color="red" label="Needs your reason for the change" /> : null}
      {warningCount > 0 ? (
        <Tag color="orange" label={warningCount === 1 ? 'Scope conflict: open for details' : `${warningCount} scope conflicts: open for details`} />
      ) : null}
      <ChangedToken id={requirement.id} changedIds={changedIds} />
    </HStack>
  )
}

function HeaderRow({
  row,
  isCollapsed,
  onToggle,
  isDropTarget,
}: {
  row: Exclude<BoardRow, { kind: 'item' }>
  isCollapsed: boolean
  onToggle: () => void
  isDropTarget: boolean
}) {
  const title = row.kind === 'section' ? SECTION_LABEL[row.section] : groupLabel(row.group)
  const hint = row.kind === 'section' ? SECTION_HINT[row.section] : GROUP_HINT[row.group]
  const header = (
    <Card padding={2} variant={isDropTarget ? 'blue' : HEADER_COLOR[row.id as keyof typeof HEADER_COLOR]}>
      <HStack gap={2} align="center" wrap="wrap">
        <IconButton
          size="sm"
          variant="ghost"
          label={`${isCollapsed ? 'Expand' : 'Collapse'} ${title}`}
          aria-expanded={!isCollapsed}
          icon={<Icon icon={isCollapsed ? 'chevronRight' : 'chevronDown'} />}
          onClick={onToggle}
        />
        <Heading level={row.kind === 'section' ? 3 : 4}>{title}</Heading>
        <Token size="sm" label={`${row.count} requirement${row.count === 1 ? '' : 's'}`} />
        <Text type="supporting">{hint}</Text>
        {row.kind === 'group' && row.count === 0 ? <Text type="supporting">· Nothing here yet</Text> : null}
        {isDropTarget ? <Token size="sm" color="blue" label={`Drop here: ${title}`} /> : null}
      </HStack>
    </Card>
  )
  // sub-groups sit indented under their section so the nesting reads at a glance
  return row.kind === 'group' ? <VStack paddingInlineStart={8}>{header}</VStack> : header
}

function boardRows(spec: LogicSpec, state: ReviewState, collapsed: Set<string>): BoardRow[] {
  const placed = placedRequirements(spec, state)
  const itemRow = (requirement: Requirement): BoardRow => ({ kind: 'item', id: requirement.id, requirement, target: targetOf(state, requirement) })
  const inGroup = (requirement: Requirement, group: Group) =>
    isCondition(group) ? targetOf(state, requirement) === group : requirement.group === group && effectivePlacement(state, requirement) === 'in'
  const group = (g: Group): BoardRow[] => {
    const id = `group-${g}`
    const members = placed.filter(({ requirement }) => inGroup(requirement, g)).map(({ requirement }) => requirement)
    return [{ kind: 'group', id, group: g, count: members.length }, ...(collapsed.has(id) ? [] : members.map(itemRow))]
  }
  const section = (key: Section, rows: () => BoardRow[]): BoardRow[] => {
    const id = `section-${key}`
    const count = placed.filter((entry) => entry.placement === key).length
    return [{ kind: 'section', id, section: key, count }, ...(collapsed.has(id) ? [] : rows())]
  }
  return [
    ...section('in', () => GROUPS.flatMap(group)),
    ...section('conditional', () => CONDITIONS.flatMap(group)),
    ...section('out', () => placed.filter((entry) => entry.placement === 'out').map((entry) => itemRow(entry.requirement))),
  ]
}

/** Where a drop on this row applies; the conditional section header names no condition, so it accepts no drops. */
function dropTarget(row: BoardRow): DropTarget | null {
  if (row.kind === 'item') return row.target
  if (row.kind === 'group') return isCondition(row.group) ? row.group : 'in'
  return row.section === 'conditional' ? null : row.section
}

/** The spec's requirements as a drag-and-drop board, grouped by placement and Claude's impact group. */
export function BoardView({ spec, state, update, changedIds }: ViewProps) {
  const [dragging, setDragging] = useState<string | null>(null)
  const [overTarget, setOverTarget] = useState<DropTarget | null>(null)
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set())
  const [openId, setOpenId] = useState<string | null>(null)
  const guard = useScopeOutGuard()
  const byId = useMemo(() => new Map(spec.requirements.map((requirement) => [requirement.id, requirement])), [spec.requirements])
  const warnings = scopeWarnings(state, spec)
  const needReason = spec.requirements.filter((requirement) => requirementMoved(state, requirement) && !state.moveReasons[requirement.id]?.trim())
  const warningCount = (id: string) => warnings.filter((message) => message.includes(id)).length
  const rows = boardRows(spec, state, collapsed)

  const toggle = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const move = (id: string, target: DropTarget) => {
    const requirement = byId.get(id)
    if (!requirement || targetOf(state, requirement) === target) return
    const baseline = placementInSpec(requirement)
    const value: Placement = target === 'in' || target === 'out' ? target : 'conditional'
    const apply = () => setPlacement(update, requirement, baseline, value, isCondition(target) ? target : undefined)
    if (target === 'out') guard(spec, state, requirement, apply)
    else apply()
  }
  const endDrag = () => {
    setDragging(null)
    setOverTarget(null)
  }

  const item = (render: (requirement: Requirement) => ReactNode) => (row: BoardRow) => (row.kind === 'item' ? render(row.requirement) : null)
  const columns: TableColumn<BoardRow>[] = [
    {
      key: 'id',
      header: 'ID',
      width: pixel(120),
      renderCell: (row) =>
        row.kind === 'item' ? (
          <VStack paddingInlineStart={row.target === 'out' ? undefined : 8}>
            <Text type="label">{row.requirement.id}</Text>
          </VStack>
        ) : null,
    },
    {
      key: 'requirement',
      header: 'Requirement',
      width: proportional(3),
      renderCell: item((requirement) => (
        <VStack gap={0.5}>
          <Link
            onClick={(e) => {
              e.stopPropagation()
              setOpenId(requirement.id)
            }}
          >
            {requirement.summary}
          </Link>
          <Text type="supporting">{requirement.area}</Text>
        </VStack>
      )),
    },
    {
      key: 'tags',
      header: 'Tags',
      width: proportional(3),
      renderCell: item((requirement) => <RowTags requirement={requirement} state={state} changedIds={changedIds} warningCount={warningCount(requirement.id)} />),
    },
  ]

  const dragPlugin: TablePlugin<BoardRow> = {
    transformBodyRow: (props, row) => {
      const target = dropTarget(row)
      const htmlProps = {
        ...props.htmlProps,
        ...(row.kind === 'item'
          ? {
              draggable: true,
              'aria-roledescription': 'Draggable requirement',
              onDragStart: (e: DragEvent<HTMLTableRowElement>) => {
                e.dataTransfer.setData('text/plain', row.id)
                e.dataTransfer.effectAllowed = 'move'
                setDragging(row.id)
              },
              onDragEnd: endDrag,
              onClick: () => setOpenId(row.id),
            }
          : {}),
        onDragOver: (e: DragEvent<HTMLTableRowElement>) => {
          if (!dragging || !target) return
          e.preventDefault()
          e.dataTransfer.dropEffect = 'move'
          if (overTarget !== target) setOverTarget(target)
        },
        onDrop: (e: DragEvent<HTMLTableRowElement>) => {
          e.preventDefault()
          if (target) move(e.dataTransfer.getData('text/plain'), target)
          endDrag()
        },
      }
      if (row.kind === 'item') return { ...props, htmlProps }
      return {
        ...props,
        htmlProps,
        children: (
          <TableCell colSpan={columns.length}>
            <HeaderRow
              row={row}
              isCollapsed={collapsed.has(row.id)}
              onToggle={() => toggle(row.id)}
              isDropTarget={Boolean(dragging) && overTarget !== null && overTarget === target && (row.kind === 'section' || isCondition(row.group))}
            />
          </TableCell>
        ),
      }
    },
  }

  return (
    <VStack gap={4}>
      <CallQueue spec={spec} state={state} update={update} changedIds={changedIds} />
      <VStack gap={1}>
        <Heading level={2}>Scope board</Heading>
        <Text type="supporting" as="p">
          The spec is everything In scope, grouped by Claude's assessment: the minimum first, then the rest by impact. Conditionally in scope
          items are built only if they fit their code budget. You decide only where each one goes: drag a row between sections or condition
          groups, or click a row to open it and change its scope and other fields. Changes to scope need a reason.
        </Text>
      </VStack>
      {needReason.length > 0 ? (
        <Banner
          status="warning"
          title={`${needReason.length} change${needReason.length === 1 ? ' needs' : 's need'} your reason`}
          description="You placed these somewhere other than Claude's proposal. Open each one and say why."
          collapsible={false}
        >
          <VStack gap={1}>
            {needReason.map((requirement) => (
              <Link key={requirement.id} onClick={() => setOpenId(requirement.id)}>{`${requirement.id} · ${requirement.summary}`}</Link>
            ))}
          </VStack>
        </Banner>
      ) : null}
      {warnings.length > 0 ? (
        <Banner status="warning" title={`${warnings.length} scope problem${warnings.length === 1 ? '' : 's'}`} collapsible={false}>
          <VStack gap={1}>
            {warnings.map((message) => (
              <Text key={message}>{message}</Text>
            ))}
          </VStack>
        </Banner>
      ) : null}
      <Table data={rows} columns={columns} plugins={{ drag: dragPlugin }} idKey="id" verticalAlign="middle" dividers="rows" hasHover />
      <RequirementDialog requirement={openId ? (byId.get(openId) ?? null) : null} spec={spec} state={state} update={update} changedIds={changedIds} onClose={() => setOpenId(null)} />
    </VStack>
  )
}
