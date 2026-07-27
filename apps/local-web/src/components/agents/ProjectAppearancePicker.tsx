import { Check } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  DEFAULT_PROJECT_COLOR,
  DEFAULT_PROJECT_ICON,
  PROJECT_COLORS,
  PROJECT_ICONS
} from '@/lib/project-appearance'
import { cn } from '@/lib/utils'

import { ProjectMark } from './ProjectMark'

export function ProjectAppearancePicker({
  icon,
  color,
  onChange
}: {
  icon: string
  color: string
  onChange: (next: { icon: string; color: string }) => void
}) {
  const [open, setOpen] = useState(false)
  const currentIcon = icon || DEFAULT_PROJECT_ICON
  const currentColor = color || DEFAULT_PROJECT_COLOR

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="hover:bg-muted/60 inline-flex shrink-0 rounded-md p-0.5"
          aria-label="Choose project icon and color"
        >
          <ProjectMark icon={currentIcon} color={currentColor} />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 space-y-3 p-3">
        <div className="flex flex-wrap gap-2">
          {PROJECT_COLORS.map(item => (
            <button
              key={item.id}
              type="button"
              aria-label={`Color ${item.id}`}
              className={cn(
                'size-6 rounded-full ring-offset-background transition',
                item.swatch,
                currentColor === item.id
                  ? 'ring-foreground ring-2 ring-offset-2'
                  : 'hover:opacity-90'
              )}
              onClick={() => onChange({ icon: currentIcon, color: item.id })}
            />
          ))}
        </div>
        <div className="grid grid-cols-8 gap-1.5">
          {PROJECT_ICONS.map(item => {
            const Icon = item.Icon
            const selected = currentIcon === item.id
            return (
              <button
                key={item.id}
                type="button"
                aria-label={`Icon ${item.id}`}
                className={cn(
                  'hover:bg-muted inline-flex size-7 items-center justify-center rounded-md',
                  selected && 'bg-muted ring-border ring-1'
                )}
                onClick={() =>
                  onChange({ icon: item.id, color: currentColor })
                }
              >
                <Icon className="size-3.5" />
              </button>
            )
          })}
        </div>
        <div className="flex justify-end">
          <Button size="sm" variant="secondary" onClick={() => setOpen(false)}>
            <Check className="size-3.5" />
            Done
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
