import { Check, Monitor, Moon, Sun } from 'lucide-react'
import { type ReactNode } from 'react'

import {
  DropdownMenuItem,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import {
  applyPalette,
  applyTheme,
  THEME_PALETTES,
  type ThemeMode,
  type ThemePaletteId
} from '@/lib/theme'
import { cn } from '@/lib/utils'

const MODE_OPTIONS: { mode: ThemeMode; label: string; Icon: typeof Sun }[] = [
  { mode: 'light', label: 'Light theme', Icon: Sun },
  { mode: 'dark', label: 'Dark theme', Icon: Moon },
  { mode: 'system', label: 'System theme', Icon: Monitor }
]

/** Borderless Light / Dark / System segment — shared by sidebar + login toggle. */
export function ThemeModeButtons({
  mode,
  className
}: {
  mode: ThemeMode
  className?: string
}) {
  return (
    <TooltipProvider delayDuration={200}>
      <div
        className={cn(
          'bg-muted/50 flex items-center gap-0.5 rounded-lg p-0.5',
          className
        )}
      >
        {MODE_OPTIONS.map(({ mode: option, label, Icon }) => (
          <Tooltip key={option}>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-label={label}
                aria-pressed={mode === option}
                onClick={event => {
                  event.preventDefault()
                  event.stopPropagation()
                  applyTheme(option)
                }}
                className={cn(
                  'text-muted-foreground inline-flex h-7 flex-1 items-center justify-center rounded-md border-0 !border-0 bg-transparent shadow-none outline-none ring-0 transition-colors focus-visible:ring-0',
                  mode === option
                    ? 'bg-card text-foreground shadow-sm'
                    : 'hover:text-foreground'
                )}
              >
                <Icon className="size-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="text-xs">
              {label}
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
    </TooltipProvider>
  )
}

/** Mode row + palette list — same layout for sidebar Theme submenu and login toggle. */
export function ThemeAppearanceMenuContent({
  mode,
  palette,
  onPreviewPalette,
  header
}: {
  mode: ThemeMode
  palette: ThemePaletteId
  onPreviewPalette?: (id: ThemePaletteId) => void
  header?: ReactNode
}) {
  return (
    <>
      {header}
      <div className="px-0.5 pb-0.5 pt-0.5">
        <ThemeModeButtons mode={mode} />
      </div>
      <DropdownMenuSeparator className="my-1" />
      {THEME_PALETTES.map(item => {
        const selected = palette === item.id
        return (
          <DropdownMenuItem
            key={item.id}
            className="flex cursor-pointer items-start gap-2.5 rounded-lg px-2.5 py-2"
            onPointerEnter={() => onPreviewPalette?.(item.id)}
            onFocus={() => onPreviewPalette?.(item.id)}
            onClick={() => applyPalette(item.id)}
          >
            <span className="mt-0.5 flex shrink-0 items-center gap-0.5">
              {item.swatches.map(color => (
                <span
                  key={color}
                  className="border-border size-3 rounded-sm border"
                  style={{ backgroundColor: color }}
                />
              ))}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium leading-tight">
                {item.name}
              </span>
              <span className="text-muted-foreground mt-0.5 block text-[11px] leading-snug">
                {item.description}
              </span>
            </span>
            {selected ? (
              <Check className="text-foreground mt-0.5 size-3.5 shrink-0" />
            ) : (
              <span className="size-3.5 shrink-0" aria-hidden />
            )}
          </DropdownMenuItem>
        )
      })}
    </>
  )
}

export { MODE_OPTIONS }
