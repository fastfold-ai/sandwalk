import { MessageSquare, SquareTerminal } from 'lucide-react'
import type { ReactNode } from 'react'

import { SandwalkMark } from '@/components/SandwalkMark'
import {
  DropdownMenuItem,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger
} from '@/components/ui/dropdown-menu'
import {
  CLI_HARNESS_PRESETS,
  type PaneSplitDirection,
  type PaneSplitTarget
} from '@/lib/pane-split'

import { SplitDownIcon, SplitRightIcon } from './split-icons'
import { TabContextItem, TabContextSeparator, TabContextSubmenu } from './tab-context-menu'

function ClaudeMark() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden className="size-3.5">
      <path
        fill="currentColor"
        d="M8 1.2 9.1 6 14 4.6 10.2 8 14 11.4 9.1 10 8 14.8 6.9 10 2 11.4 5.8 8 2 4.6 6.9 6Z"
      />
    </svg>
  )
}

function CodexMark() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden className="size-3.5">
      <circle cx="8" cy="8" r="2.1" fill="currentColor" />
      <circle cx="8" cy="2.4" r="1.15" fill="currentColor" />
      <circle cx="12.6" cy="5.2" r="1.15" fill="currentColor" />
      <circle cx="12.6" cy="10.8" r="1.15" fill="currentColor" />
      <circle cx="8" cy="13.6" r="1.15" fill="currentColor" />
      <circle cx="3.4" cy="10.8" r="1.15" fill="currentColor" />
      <circle cx="3.4" cy="5.2" r="1.15" fill="currentColor" />
    </svg>
  )
}

function targetIcon(id: PaneSplitTarget): ReactNode {
  if (id === 'agent') return <MessageSquare className="size-3.5" />
  if (id === 'terminal') return <SquareTerminal className="size-3.5" />
  if (id === 'claude') return <ClaudeMark />
  if (id === 'codex') return <CodexMark />
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

/** Same Split Down / Split Right choices, for Radix dropdown menus. */
export function SplitMenuDropdown({
  sourceId,
  onSplitPane
}: {
  sourceId: string
  onSplitPane: (
    sourceId: string,
    direction: PaneSplitDirection,
    target: PaneSplitTarget
  ) => void
}) {
  const flyout = (direction: PaneSplitDirection) =>
    TARGETS.map(target => (
      <DropdownMenuItem
        key={target.id}
        className="gap-2 text-[13px]"
        onSelect={() => onSplitPane(sourceId, direction, target.id)}
      >
        {targetIcon(target.id)}
        {target.label}
      </DropdownMenuItem>
    ))

  return (
    <>
      <DropdownMenuSub>
        <DropdownMenuSubTrigger className="gap-2 text-[13px] [&_svg]:size-3.5">
          <SplitDownIcon />
          Split Down
          <DropdownMenuShortcut>⇧⌘D</DropdownMenuShortcut>
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="min-w-[11rem]">
          {flyout('vertical')}
        </DropdownMenuSubContent>
      </DropdownMenuSub>
      <DropdownMenuSub>
        <DropdownMenuSubTrigger className="gap-2 text-[13px] [&_svg]:size-3.5">
          <SplitRightIcon />
          Split Right
          <DropdownMenuShortcut>⌘D</DropdownMenuShortcut>
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="min-w-[11rem]">
          {flyout('horizontal')}
        </DropdownMenuSubContent>
      </DropdownMenuSub>
    </>
  )
}
