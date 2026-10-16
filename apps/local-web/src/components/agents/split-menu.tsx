import { MessageSquare, SquareTerminal } from 'lucide-react'
import type { ReactNode } from 'react'

import { SandwalkMark } from '@/components/SandwalkMark'
import {
  CLI_HARNESS_PRESETS,
  type PaneSplitDirection,
  type PaneSplitTarget
} from '@/lib/pane-split'

import { ExternalAgentIcon, isExternalAgentKind } from './ExternalAgentIcon'
import { SplitDownIcon, SplitRightIcon } from './split-icons'
import { TabContextItem, TabContextSeparator, TabContextSubmenu } from './tab-context-menu'

function targetIcon(id: PaneSplitTarget): ReactNode {
  if (id === 'agent') return <MessageSquare className="size-3.5" />
  if (id === 'terminal') return <SquareTerminal className="size-3.5" />
  if (isExternalAgentKind(id)) return <ExternalAgentIcon kind={id} />
  return <SandwalkMark className="size-3.5" />
}

const TARGETS: { id: PaneSplitTarget; label: string }[] = [
  { id: 'agent', label: 'Agent' },
  { id: 'terminal', label: 'Terminal' },
  ...CLI_HARNESS_PRESETS.map(preset => ({
    id: preset.id,
    label: preset.title
  }))
]

export function SplitMenuBlock({
  sourceId,
  onSplitPane,
  trailingSeparator = true
}: {
  sourceId: string
  onSplitPane: (
    sourceId: string,
    direction: PaneSplitDirection,
    target: PaneSplitTarget
  ) => void
  trailingSeparator?: boolean
}) {
  const flyout = (direction: PaneSplitDirection) =>
    TARGETS.map(target => (
      <TabContextItem
        key={target.id}
        icon={targetIcon(target.id)}
        label={target.label}
        onClick={() => onSplitPane(sourceId, direction, target.id)}
      />
    ))

  return (
    <>
      <TabContextSubmenu
        icon={<SplitDownIcon />}
        label="Split Down"
        trailing={<span className="text-[11px] tabular-nums">⇧⌘D</span>}
      >
        {flyout('vertical')}
      </TabContextSubmenu>
      <TabContextSubmenu
        icon={<SplitRightIcon />}
        label="Split Right"
        trailing={<span className="text-[11px] tabular-nums">⌘D</span>}
      >
        {flyout('horizontal')}
      </TabContextSubmenu>
      {trailingSeparator ? <TabContextSeparator /> : null}
    </>
  )
}