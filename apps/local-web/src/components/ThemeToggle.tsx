import { Check, ChevronUp, Monitor, Moon, Palette, Sun } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

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

const MODE_OPTIONS: { mode: ThemeMode; label: string; Icon: typeof Sun }[] = [
  { mode: 'light', label: 'Light theme', Icon: Sun },
  { mode: 'dark', label: 'Dark theme', Icon: Moon },
  { mode: 'system', label: 'System theme', Icon: Monitor }
]

const PORTAL_ATTR = 'data-sandwalk-theme-toggle'

/**
 * Login appearance control.
 *
 * Uses a viewport-locked overlay (`fixed inset-0`) so `right`/`bottom` are
 * always relative to the visible window — never Mirage/Login overflow boxes.
 */
export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() => getStoredTheme())
  const [palette, setPalette] = useState<ThemePaletteId>(() =>
    getStoredPalette()
  )
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    document.querySelectorAll(`[${PORTAL_ATTR}]`).forEach(node => node.remove())
    setMounted(true)
  }, [])

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

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
        previewPalette(getStoredPalette())
      }
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onPointer)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onPointer)
    }
  }, [open])

  const activePalette =
    THEME_PALETTES.find(item => item.id === palette) ?? THEME_PALETTES[0]

  const restorePalette = () => previewPalette(getStoredPalette())

  if (!mounted || typeof document === 'undefined') return null

  return createPortal(
    <div
      data-sandwalk-theme-toggle="overlay"
      className="pointer-events-none fixed inset-0 z-[100]"
    >
      <div
        ref={rootRef}
        className="pointer-events-auto absolute bottom-6 right-6 flex w-[min(16rem,calc(100vw-3rem))] flex-col items-stretch gap-2"
      >
        {open ? (
          <div
            role="menu"
            aria-label="Appearance"
            className="bg-card w-full rounded-xl border p-1.5 shadow-xl"
            onPointerLeave={restorePalette}
          >
            <div
              className="flex items-center gap-0.5 p-0.5"
              role="group"
              aria-label="Color mode"
            >
              {MODE_OPTIONS.map(({ mode: option, label, Icon }) => (
                <button
                  key={option}
                  type="button"
                  role="menuitemradio"
                  aria-label={label}
                  title={label}
                  aria-checked={mode === option}
                  onClick={() => applyTheme(option)}
                  className={cn(
                    'text-muted-foreground inline-flex h-8 flex-1 items-center justify-center rounded-md border-0 bg-transparent shadow-none outline-none transition-colors',
                    mode === option
                      ? 'bg-muted text-foreground'
                      : 'hover:bg-muted/60 hover:text-foreground'
                  )}
                >
                  <Icon className="size-3.5" />
                </button>
              ))}
            </div>

            <div className="bg-border my-1.5 h-px" aria-hidden />

            {THEME_PALETTES.map(item => {
              const selected = palette === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={selected}
                  className="hover:bg-muted/60 flex w-full cursor-pointer items-start gap-2.5 rounded-lg border-0 bg-transparent px-2.5 py-2 text-left outline-none"
                  onPointerEnter={() => previewPalette(item.id)}
                  onFocus={() => previewPalette(item.id)}
                  onClick={() => {
                    applyPalette(item.id)
                    setOpen(false)
                  }}
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
                    <span className="text-foreground block text-sm font-medium leading-tight">
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
                </button>
              )
            })}
          </div>
        ) : null}

        <button
          type="button"
          aria-label={`Appearance: ${activePalette.name}`}
          aria-expanded={open}
          aria-haspopup="menu"
          title={`Appearance: ${activePalette.name}`}
          onClick={() => {
            if (open) restorePalette()
            setOpen(current => !current)
          }}
          className="text-muted-foreground hover:bg-muted/60 hover:text-foreground ml-auto inline-flex h-9 items-center gap-1.5 rounded-xl border-0 bg-transparent px-2.5 text-xs font-medium shadow-none transition-colors"
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
          <ChevronUp
            className={cn(
              'size-3 shrink-0 opacity-60 transition-transform',
              open && 'rotate-180'
            )}
          />
        </button>
      </div>
    </div>,
    document.body
  )
}
