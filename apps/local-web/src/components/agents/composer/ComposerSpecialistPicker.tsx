import type { Specialist } from '@sandwalk/agent-ui-core'
import { Check, ChevronDown, Plus } from 'lucide-react'
import { useState } from 'react'

import {
  specialistColorClass,
  SpecialistGlyph
} from '@/components/agents/SpecialistsView'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

export function ComposerSpecialistPicker({
  specialists,
  selectedSpecialistId = null,
  onSpecialistSelect,
  onCreateSpecialist,
  onManageSpecialists
}: {
  specialists: Specialist[]
  selectedSpecialistId?: string | null
  onSpecialistSelect: (specialistId: string | null) => void | Promise<void>
  onCreateSpecialist?: () => void
  onManageSpecialists?: () => void
}) {
  const [specialistPickerOpen, setSpecialistPickerOpen] = useState(false)

  const selectedSpecialist =
    specialists.find(item => item.id === selectedSpecialistId) || null

  return (
    <Popover
      open={specialistPickerOpen}
      onOpenChange={setSpecialistPickerOpen}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground inline-flex w-[8.5rem] shrink-0 items-center gap-1.5 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
        >
          {selectedSpecialist ? (
            <span
              className={cn(
                'flex size-3.5 shrink-0 items-center justify-center rounded-full text-white [&_svg]:text-white',
                specialistColorClass(selectedSpecialist.color)
              )}
            >
              <SpecialistGlyph
                icon={selectedSpecialist.icon}
                className="size-2 text-white"
              />
            </span>
          ) : (
            <span className="bg-muted-foreground/40 size-1.5 shrink-0 rounded-full" />
          )}
          <span className="min-w-0 flex-1 truncate text-left font-medium">
            {selectedSpecialist?.name || 'None'}
          </span>
          <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        side="top"
        className="w-64 overflow-hidden p-0"
        onCloseAutoFocus={event => event.preventDefault()}
      >
        <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
          <span className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
            Specialist
          </span>
          {onManageSpecialists ? (
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground text-[11px] font-normal"
              onClick={() => {
                setSpecialistPickerOpen(false)
                onManageSpecialists()
              }}
            >
              Manage
            </button>
          ) : null}
        </div>
        <ScrollArea className="h-72 w-full">
          <div className="py-1">
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm"
              onClick={() => {
                void onSpecialistSelect(null)
                setSpecialistPickerOpen(false)
              }}
            >
              <span className="bg-muted-foreground/40 size-2.5 shrink-0 rounded-full" />
              <span className="truncate">None</span>
              {!selectedSpecialistId ? (
                <Check className="text-foreground ml-auto size-4 shrink-0" />
              ) : null}
            </button>
            {specialists
              .filter(item => item.enabled !== false)
              .map(item => {
                const isSelected = item.id === selectedSpecialistId
                return (
                  <button
                    key={item.id}
                    type="button"
                    className="hover:bg-muted flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm"
                    onClick={() => {
                      void onSpecialistSelect(item.id)
                      setSpecialistPickerOpen(false)
                    }}
                  >
                    <span
                      className={cn(
                        'flex size-4 shrink-0 items-center justify-center rounded-full text-white [&_svg]:text-white',
                        specialistColorClass(item.color)
                      )}
                    >
                      <SpecialistGlyph
                        icon={item.icon}
                        className="size-2.5 text-white"
                      />
                    </span>
                    <span className="min-w-0 flex-1 truncate">{item.name}</span>
                    {isSelected ? (
                      <Check className="text-foreground ml-auto size-4 shrink-0" />
                    ) : null}
                  </button>
                )
              })}
          </div>
        </ScrollArea>
        {onCreateSpecialist ? (
          <div className="border-t p-1">
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setSpecialistPickerOpen(false)
                onCreateSpecialist()
              }}
            >
              <Plus className="size-3.5" />
              Create new…
            </button>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}
