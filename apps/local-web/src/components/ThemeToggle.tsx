import { Check, ChevronUp, Monitor, Moon, Palette, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  applyPalette,
  applyTheme,
  getStoredPalette,
  getStoredTheme,
  PALETTE_CHANGE_EVENT,
  previewPalette,
  THEME_CHANGE_EVENT,
  THEME_PALETTES,
  type ThemeMode,
  type ThemePaletteId
} from '@/lib/theme'
import { cn } from '@/lib/utils'

const OPTIONS: { mode: ThemeMode; label: string; Icon: typeof Sun }[] = [
  { mode: 'light', label: 'Light theme', Icon: Sun },
  { mode: 'system', label: 'System theme', Icon: Monitor },
  { mode: 'dark', label: 'Dark theme', Icon: Moon }
]

/** Floating theme switcher — ghost style (login page). */
export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() => getStoredTheme())
  const [palette, setPalette] = useState<ThemePaletteId>(() =>
    getStoredPalette()
  )

  useEffect(() => {
    const onMode = (event: Event) => {
      setMode((event as CustomEvent<ThemeMode>).detail)
    }
    const onPalette = (event: Event) => {
      setPalette((event as CustomEvent<ThemePaletteId>).detail)
    }
    window.addEventListener(THEME_CHANGE_EVENT, onMode)
    window.addEventListener(PALETTE_CHANGE_EVENT, onPalette)
    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, onMode)
      window.removeEventListener(PALETTE_CHANGE_EVENT, onPalette)
    }
  }, [])

  const activePalette =
    THEME_PALETTES.find(item => item.id === palette) ?? THEME_PALETTES[0]

  const restorePalette = () => previewPalette(getStoredPalette())

  return (
    <div
      className="fixed right-4 bottom-4 z-50 flex items-center gap-0.5 rounded-lg p-1"
      role="group"
      aria-label="Theme"
    >
      <DropdownMenu
        onOpenChange={open => {
          if (!open) restorePalette()
        }}
      >
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Color palette: ${activePalette.name}`}
            title={`Color palette: ${activePalette.name}`}
            className="text-muted-foreground hover:bg-muted/60 hover:text-foreground inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium transition-colors"
          >
            <Palette className="size-3.5 shrink-0" />
            <span className="max-w-[4.5rem] truncate">{activePalette.name}</span>
            <span className="flex items-center gap-0.5">
              {activePalette.swatches.map(color => (
                <span
                  key={color}
                  className="border-border/60 size-2 rounded-full border"
                  style={{ backgroundColor: color }}
                />
              ))}
            </span>
            <ChevronUp className="size-3 shrink-0 opacity-60" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          side="top"
          sideOffset={10}
          className="bg-card w-64 rounded-xl border p-1.5 shadow-xl"
          onPointerLeave={restorePalette}
          onCloseAutoFocus={restorePalette}
        >
          <DropdownMenuLabel className="text-muted-foreground px-2 py-1.5 text-xs font-medium">
            Color palette
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {THEME_PALETTES.map(item => {
            const selected = palette === item.id
            return (
              <DropdownMenuItem
                key={item.id}
                className="flex cursor-pointer items-start gap-2.5 rounded-lg px-2.5 py-2"
                onPointerEnter={() => previewPalette(item.id)}
                onFocus={() => previewPalette(item.id)}
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
        </DropdownMenuContent>
      </DropdownMenu>

      <span className="bg-border/50 mx-0.5 h-4 w-px shrink-0" aria-hidden />

      {OPTIONS.map(({ mode: option, label, Icon }) => (
        <button
          key={option}
          type="button"
          aria-label={label}
          title={label}
          aria-pressed={mode === option}
          onClick={() => applyTheme(option)}
          className={cn(
            'text-muted-foreground hover:bg-muted/60 hover:text-foreground inline-flex size-8 items-center justify-center rounded-md transition-colors',
            mode === option && 'bg-muted/70 text-foreground'
          )}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  )
}
