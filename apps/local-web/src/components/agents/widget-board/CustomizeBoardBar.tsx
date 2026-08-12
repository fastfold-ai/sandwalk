import {
  ChartColumn,
  ChevronDown,
  List,
  Plus,
  RotateCcw,
  SquareStack,
  type LucideIcon
} from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'

import { catalogForSurface } from './catalog'
import type { WidgetSurface, WidgetType, WidgetVisual } from './types'

const VISUAL_ICON: Record<WidgetVisual, LucideIcon> = {
  card: SquareStack,
  plot: ChartColumn,
  list: List
}

const VISUAL_LABEL: Record<WidgetVisual, string> = {
  card: 'Card',
  plot: 'Plot',
  list: 'List'
}

export function AddWidgetButton({
  surface,
  presentTypes,
  onAdd,
  onReset
}: {
  surface: WidgetSurface
  presentTypes: Set<string>
  onAdd: (type: WidgetType) => void
  onReset?: () => void
}) {
  const [open, setOpen] = useState(false)
  const available = catalogForSurface(surface).filter(
    entry => !presentTypes.has(entry.type)
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" size="sm" variant="ghost">
          <Plus className="size-3.5" />
          Add widget
          <ChevronDown className="size-3.5 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-1">
        {available.length === 0 ? (
          <p className="text-muted-foreground px-2.5 py-2 text-xs">
            All widgets are already on the board.
          </p>
        ) : (
          available.map(entry => {
            const Icon = VISUAL_ICON[entry.visual]
            return (
              <button
                key={entry.type}
                type="button"
                className="hover:bg-muted flex w-full items-start gap-2.5 rounded-md px-2.5 py-2 text-left"
                onClick={() => {
                  onAdd(entry.type)
                  setOpen(false)
                }}
              >
                <span
                  className="bg-muted text-muted-foreground mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md"
                  title={VISUAL_LABEL[entry.visual]}
                  aria-label={VISUAL_LABEL[entry.visual]}
                >
                  <Icon className="size-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5 text-sm font-medium">
                    {entry.title}
                    <span className="text-muted-foreground text-[10px] font-normal uppercase tracking-wide">
                      {VISUAL_LABEL[entry.visual]}
                    </span>
                  </span>
                  <span className="text-muted-foreground block text-xs">
                    {entry.description}
                  </span>
                </span>
              </button>
            )
          })
        )}
        {onReset ? (
          <>
            <div className="bg-border my-1 h-px" />
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left"
              onClick={() => {
                onReset()
                setOpen(false)
              }}
            >
              <span className="bg-muted text-muted-foreground flex size-7 shrink-0 items-center justify-center rounded-md">
                <RotateCcw className="size-3.5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">Reset layout</span>
                <span className="text-muted-foreground block text-xs">
                  Restore the default widgets for this board
                </span>
              </span>
            </button>
          </>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}

export function CustomizeBoardBar({
  surface,
  presentTypes,
  onAdd,
  onReset
}: {
  surface: WidgetSurface
  presentTypes: Set<string>
  onAdd: (type: WidgetType) => void
  onReset?: () => void
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
      <AddWidgetButton
        surface={surface}
        presentTypes={presentTypes}
        onAdd={onAdd}
        onReset={onReset}
      />
    </div>
  )
}
