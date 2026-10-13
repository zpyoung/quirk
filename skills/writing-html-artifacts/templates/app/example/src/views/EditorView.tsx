import { useMemo } from 'react'
import { createColumnHelper, tableFeatures, useTable } from '@tanstack/react-table'
import { Button } from '@astryxdesign/core/Button'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { NumberInput } from '@astryxdesign/core/NumberInput'
import { Switch } from '@astryxdesign/core/Switch'
import { Text } from '@astryxdesign/core/Text'
import { TextInput } from '@astryxdesign/core/TextInput'
import { useFlags, type Flag } from '../flags'

const features = tableFeatures({})
const column = createColumnHelper<typeof features, Flag>()

export function EditorView() {
  const { flags, update, reset } = useFlags()
  const columns = useMemo(
    () =>
      column.columns([
        column.accessor('name', {
          header: 'Flag',
          cell: ({ row }) => (
            <VStack gap={0.5}>
              <Text weight="semibold">{row.original.name}</Text>
              <Text type="supporting" color="secondary">{row.original.description}</Text>
            </VStack>
          ),
        }),
        column.accessor('enabled', {
          header: 'Enabled',
          cell: ({ row }) => (
            <Switch
              label={`Enable ${row.original.name}`}
              isLabelHidden
              value={row.original.enabled}
              onChange={(enabled) => update(row.original.id, { enabled })}
            />
          ),
        }),
        column.accessor('rollout', {
          header: 'Rollout %',
          cell: ({ row }) => (
            <NumberInput
              label={`Rollout percent for ${row.original.name}`}
              isLabelHidden
              value={row.original.rollout}
              min={0}
              max={100}
              isIntegerOnly
              onChange={(rollout) => update(row.original.id, { rollout })}
              width={120}
            />
          ),
        }),
        column.accessor('owner', {
          header: 'Owner',
          cell: ({ row }) => (
            <TextInput
              label={`Owner of ${row.original.name}`}
              isLabelHidden
              value={row.original.owner}
              onChange={(owner) => update(row.original.id, { owner })}
              width={160}
            />
          ),
        }),
      ]),
    [update],
  )
  const table = useTable({ features, columns, data: flags })

  return (
    <VStack gap={3}>
      <HStack gap={2} justify="between" align="center" wrap="wrap">
        <Text color="secondary">Edit any cell. The Preview tab reads the same flags.</Text>
        <Button label="Reset to defaults" variant="secondary" size="sm" onClick={reset} />
      </HStack>
      <div className="q-table-wrap">
        <table className="q-grid" aria-label="Feature flags">
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th key={header.id} scope="col">
                    {header.isPlaceholder ? null : <table.FlexRender header={header} />}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getAllCells().map((cell) => (
                  <td key={cell.id}>
                    <table.FlexRender cell={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </VStack>
  )
}
