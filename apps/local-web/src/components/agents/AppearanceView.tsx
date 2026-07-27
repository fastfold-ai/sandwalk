import { Check, ChevronDown, Monitor, Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { isMacDesktopOverlay, isTauri, platformOS } from '@/lib/desktop'
import {
  APP_FONT_CHANGE_EVENT,
  APP_FONTS,
  type AppFontId,
  applyAppFont,
  applyDockIcon,
  applyTheme,
  applyUiFontSize,
  DOCK_ICON_CHANGE_EVENT,
  type DockIconId,
  getStoredAppFont,
  getStoredDockIcon,
  getStoredPalette,
  getStoredTheme,
  getStoredUiFontSize,
  PALETTE_CHANGE_EVENT,
  THEME_CHANGE_EVENT,
  type ThemeMode,
  type ThemePaletteId,
  UI_FONT_SIZE_CHANGE_EVENT,
  UI_FONT_SIZE_MAX,
  UI_FONT_SIZE_MIN} from '@/lib/theme'
import { cn } from '@/lib/utils'

import { GeneralViewThemesSection } from './general-view-themes'

function isMacDesktop() {
  return isMacDesktopOverlay() || (isTauri() && platformOS() === 'macos')
}

const DOCK_ICON_OPTIONS: {
  id: DockIconId
  label: string
  src: string
}[] = [
  { id: 'system', label: 'Default', src: '/dock-icons/light.png' },
  { id: 'golden', label: 'Golden', src: '/dock-icons/golden.png' },
  { id: 'dark', label: 'Dark', src: '/dock-icons/dark.png' }
]

function AppearanceDockIconSection({ dockIcon }: { dockIcon: DockIconId }) {
  return (
    <section className="space-y-3">
      <h3 className="text-base font-semibold">Dock icon</h3>
      <div className="flex items-center gap-3">
        {DOCK_ICON_OPTIONS.map(({ id, label, src }) => {
          const selected = dockIcon === id
          return (
            <button
              key={id}
              type="button"
              title={label}
              aria-label={label}
              onClick={() => applyDockIcon(id)}
              className={cn(
                'relative flex size-14 items-center justify-center rounded-2xl border p-1.5 transition-colors',
                selected ? 'border-primary' : 'border-border hover:border-muted-foreground/40'
              )}
            >
              <img
                src={src}
                alt={label}
                className="size-full rounded-xl object-cover"
              />
              {selected ? (
                <span className="bg-primary text-primary-foreground absolute -bottom-1 -right-1 inline-flex size-5 items-center justify-center rounded-full ring-2 ring-background">
                  <Check className="size-3" />
                </span>
              ) : null}
            </button>
          )
        })}
      </div>
    </section>
  )
}

const MODE_OPTIONS: { mode: ThemeMode; label: string; Icon: typeof Sun }[] = [
  { mode: 'light', label: 'Light', Icon: Sun },
  { mode: 'dark', label: 'Dark', Icon: Moon },
  { mode: 'system', label: 'System', Icon: Monitor }
]

function AppearanceModeSection({ mode }: { mode: ThemeMode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-base font-semibold">Theme</h3>
      <div className="grid max-w-md gap-2 sm:grid-cols-3">
        {MODE_OPTIONS.map(({ mode: option, label, Icon }) => {
          const selected = mode === option
          return (
            <button
              key={option}
              type="button"
              onClick={() => applyTheme(option)}
              className={cn(
                'bg-card hover:bg-muted/40 flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors',
                selected ? 'border-primary text-foreground' : 'border-border text-muted-foreground'
              )}
            >
              <Icon className="size-3.5 shrink-0" />
              <span className="truncate font-medium">{label}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}

function AppearanceFontRow({ font }: { font: AppFontId }) {
  const current = APP_FONTS.find(item => item.id === font) ?? APP_FONTS[0]
  return (
    <div className="border-border/70 flex items-center justify-between gap-3 rounded-xl border p-4">
      <div>
        <div className="text-sm font-medium">Font</div>
        <p className="text-muted-foreground mt-0.5 text-xs">
          Choose the typeface used across the app.
        </p>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="border-border bg-card text-foreground focus-visible:ring-ring flex h-9 min-w-48 shrink-0 items-center justify-between gap-2 rounded-md border px-3 text-sm outline-none focus-visible:ring-1"
          >
            <span
              className="truncate"
              style={{ fontFamily: current.stack }}
            >
              {current.label}
            </span>
            <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="max-h-72 w-56 overflow-y-auto"
        >
          {APP_FONTS.map(item => {
            const selected = item.id === font
            return (
              <DropdownMenuItem
                key={item.id}
                onSelect={() => applyAppFont(item.id)}
                className={cn(selected && 'text-primary')}
              >
                <Check
                  className={cn('size-3.5 shrink-0', !selected && 'invisible')}
                />
                <span className="truncate" style={{ fontFamily: item.stack }}>
                  {item.label}
                </span>
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

function AppearancePreferencesSection({
  fontSize,
  font
}: {
  fontSize: number
  font: AppFontId
}) {
  return (
    <section className="space-y-4">
      <h3 className="text-base font-semibold">Preferences</h3>

      <AppearanceFontRow font={font} />

      <div className="border-border/70 flex items-center justify-between gap-3 rounded-xl border p-4">
        <div>
          <div className="text-sm font-medium">UI font size</div>
          <p className="text-muted-foreground mt-0.5 text-xs">
            Scales text and spacing across the app.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <input
            type="number"
            inputMode="numeric"
            min={UI_FONT_SIZE_MIN}
            max={UI_FONT_SIZE_MAX}
            step={1}
            value={fontSize}
            onChange={event => {
              const next = Number(event.target.value)
              if (Number.isFinite(next)) applyUiFontSize(next)
            }}
            className="border-border bg-card text-foreground focus-visible:ring-ring h-8 w-14 rounded-md border px-2 text-center text-sm outline-none [appearance:textfield] focus-visible:ring-1 [&::-webkit-inner-spin-button]:opacity-100 [&::-webkit-outer-spin-button]:opacity-100"
          />
          <span className="text-muted-foreground text-xs">px</span>
        </div>
      </div>
    </section>
  )
}

export function AppearanceView() {
  const [mode, setMode] = useState<ThemeMode>(() => getStoredTheme())
  const [palette, setPalette] = useState<ThemePaletteId>(() => getStoredPalette())
  const [fontSize, setFontSize] = useState(() => getStoredUiFontSize())
  const [font, setFont] = useState<AppFontId>(() => getStoredAppFont())
  const [dockIcon, setDockIcon] = useState<DockIconId>(() => getStoredDockIcon())
  const [macDesktop, setMacDesktop] = useState(() => isMacDesktop())

  useEffect(() => {
    setMacDesktop(isMacDesktop())
    const onMode = (event: Event) => {
      setMode((event as CustomEvent<ThemeMode>).detail)
    }
    const onPalette = (event: Event) => {
      setPalette((event as CustomEvent<ThemePaletteId>).detail)
    }
    const onFontSize = (event: Event) => {
      setFontSize((event as CustomEvent<number>).detail)
    }
    const onFont = (event: Event) => {
      setFont((event as CustomEvent<AppFontId>).detail)
    }
    const onDockIcon = (event: Event) => {
      setDockIcon((event as CustomEvent<DockIconId>).detail)
    }
    window.addEventListener(THEME_CHANGE_EVENT, onMode)
    window.addEventListener(PALETTE_CHANGE_EVENT, onPalette)
    window.addEventListener(UI_FONT_SIZE_CHANGE_EVENT, onFontSize)
    window.addEventListener(APP_FONT_CHANGE_EVENT, onFont)
    window.addEventListener(DOCK_ICON_CHANGE_EVENT, onDockIcon)
    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, onMode)
      window.removeEventListener(PALETTE_CHANGE_EVENT, onPalette)
      window.removeEventListener(UI_FONT_SIZE_CHANGE_EVENT, onFontSize)
      window.removeEventListener(APP_FONT_CHANGE_EVENT, onFont)
      window.removeEventListener(DOCK_ICON_CHANGE_EVENT, onDockIcon)
    }
  }, [])

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl space-y-10 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        <h2 className="text-2xl font-semibold">Appearance</h2>

        <AppearanceModeSection mode={mode} />

        <GeneralViewThemesSection palette={palette} />

        {macDesktop ? <AppearanceDockIconSection dockIcon={dockIcon} /> : null}

        <AppearancePreferencesSection fontSize={fontSize} font={font} />
      </div>
    </ScrollArea>
  )
}
