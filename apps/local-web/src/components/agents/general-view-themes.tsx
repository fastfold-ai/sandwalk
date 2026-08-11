import { Check } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Slider } from '@/components/ui/slider'
import { isMacDesktopOverlay, isTauri, platformOS } from '@/lib/desktop'
import {
  ACCENT_COLOR_CHANGE_EVENT,
  ACCENT_COLORS,
  type AccentColorId,
  applyAccentColor,
  applyCustomTheme,
  applyGlassMaterial,
  applyGlassTintStrength,
  applyLiquidGlass,
  applyPalette,
  CUSTOM_THEME_CHANGE_EVENT,
  type CustomThemeColors,
  getStoredAccentColor,
  getStoredCustomTheme,
  getStoredGlassMaterial,
  getStoredGlassTintStrength,
  getStoredLiquidGlass,
  getStoredPalette,
  GLASS_MATERIAL_CHANGE_EVENT,
  GLASS_MATERIALS,
  GLASS_TINT_STRENGTH_CHANGE_EVENT,
  GLASS_TINT_STRENGTH_MAX,
  GLASS_TINT_STRENGTH_MIN,
  type GlassMaterialId,
  LIQUID_GLASS_CHANGE_EVENT,
  previewAccentColor,
  previewPalette,
  resetAppearanceDefaults,
  resolveAutoTextHex,
  resolvePaletteAccentSwatch,
  THEME_PALETTES,
  type ThemePaletteId,
  type ThemePaletteMeta
} from '@/lib/theme'
import { cn } from '@/lib/utils'

function showLiquidGlassOption() {
  return (
    isMacDesktopOverlay() ||
    (isTauri() && platformOS() === 'macos')
  )
}

type CustomColorFieldId = 'nav' | 'selected' | 'presence'

const CUSTOM_COLOR_FIELDS: { id: CustomColorFieldId; label: string }[] = [
  { id: 'nav', label: 'System navigation' },
  { id: 'selected', label: 'Selected items' },
  { id: 'presence', label: 'Presence indication' }
]

function CustomThemeTab({
  colors,
  onChange
}: {
  colors: CustomThemeColors
  onChange: (next: CustomThemeColors) => void
}) {
  return (
    <div className="space-y-4">
      <div className="text-sm font-semibold">Theme colors</div>
      <div className="grid gap-3 sm:grid-cols-2">
        {CUSTOM_COLOR_FIELDS.map(field => (
          <div key={field.id} className="space-y-1.5">
            <div className="text-xs font-medium">{field.label}</div>
            <div
              className={cn(
                'border-border bg-card flex items-center gap-2.5 rounded-full border py-1 pl-1 pr-3 text-left'
              )}
            >
              <span className="relative size-7 shrink-0">
                <span
                  className="border-border/60 pointer-events-none block size-7 rounded-full border"
                  style={{ backgroundColor: colors[field.id] }}
                />
                <input
                  type="color"
                  value={colors[field.id]}
                  onChange={event =>
                    onChange({ ...colors, [field.id]: event.target.value })
                  }
                  className="absolute inset-0 size-full cursor-pointer rounded-full opacity-0"
                  title={`Pick a color for ${field.label}`}
                  aria-label={`${field.label} color picker`}
                />
              </span>
              <input
                type="text"
                value={colors[field.id].toUpperCase()}
                onChange={event =>
                  onChange({ ...colors, [field.id]: event.target.value })
                }
                spellCheck={false}
                className="text-foreground min-w-0 flex-1 bg-transparent font-mono text-xs outline-none"
              />
            </div>
          </div>
        ))}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-xs font-medium">Text color</div>
            {colors.text ? (
              <button
                type="button"
                onClick={() => onChange({ ...colors, text: null })}
                className="text-muted-foreground hover:text-foreground text-[11px]"
              >
                Reset to auto
              </button>
            ) : null}
          </div>
          <div
            className={cn(
              'border-border bg-card flex items-center gap-2.5 rounded-full border py-1 pl-1 pr-3 text-left'
            )}
          >
            <span className="relative size-7 shrink-0">
              <span
                className="border-border/60 pointer-events-none block size-7 rounded-full border"
                style={{
                  backgroundColor: colors.text ?? resolveAutoTextHex(colors.nav)
                }}
              />
              <input
                type="color"
                value={colors.text ?? resolveAutoTextHex(colors.nav)}
                onChange={event => onChange({ ...colors, text: event.target.value })}
                className="absolute inset-0 size-full cursor-pointer rounded-full opacity-0"
                title="Pick a text color"
                aria-label="Text color picker"
              />
            </span>
            <input
              type="text"
              value={(colors.text ?? resolveAutoTextHex(colors.nav)).toUpperCase()}
              onChange={event => onChange({ ...colors, text: event.target.value })}
              spellCheck={false}
              className="text-foreground min-w-0 flex-1 bg-transparent font-mono text-xs outline-none"
            />
          </div>
          <p className="text-muted-foreground text-[11px]">
            {colors.text
              ? 'Custom color applied in both light and dark.'
              : 'Auto — dark ink on light nav, light ink on dark nav.'}
          </p>
        </div>
      </div>
      <label className="flex cursor-pointer items-start gap-2.5">
        <input
          type="checkbox"
          checked={colors.gradient}
          onChange={event =>
            onChange({ ...colors, gradient: event.target.checked })
          }
          className="accent-foreground mt-0.5 size-3.5"
        />
        <span className="text-sm">
          <span className="font-medium">Window gradient</span>
          <span className="text-muted-foreground block text-xs">
            Blend System navigation and Selected items colors together in
            the sidebar background.
          </span>
        </span>
      </label>
    </div>
  )
}

/** Slack-style blended circle — bright center fading through mid into a deep rim. */
function paletteSwatchBackground(swatches: [string, string, string]) {
  const [center, mid, rim] = swatches
  return `radial-gradient(circle at 32% 28%, ${center} 0%, ${mid} 42%, ${rim} 100%)`
}

function PaletteGrid({
  palettes,
  palette
}: {
  palettes: ThemePaletteMeta[]
  palette: ThemePaletteId
}) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {palettes.map(item => {
        const selected = palette === item.id
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              applyPalette(item.id)
              applyAccentColor('none')
            }}
            onPointerEnter={() => previewPalette(item.id)}
            onPointerLeave={() => previewPalette(getStoredPalette())}
            onFocus={() => previewPalette(item.id)}
            onBlur={() => previewPalette(getStoredPalette())}
            title={item.description}
            className={cn(
              'bg-card hover:bg-muted/40 flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors',
              selected ? 'border-primary ring-primary/20 ring-2' : 'border-border'
            )}
          >
            <span
              className="border-border/50 size-6 shrink-0 rounded-full border shadow-sm"
              style={{ backgroundImage: paletteSwatchBackground(item.swatches) }}
            />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">
              {item.name}
            </span>
            {selected ? (
              <Check className="text-primary size-3.5 shrink-0" />
            ) : null}
          </button>
        )
      })}
    </div>
  )
}

function AccentColorRow({
  accent,
  defaultSwatch
}: {
  accent: AccentColorId
  /** The active palette/custom theme's own accent — shown for the "Default" dot. */
  defaultSwatch: string
}) {
  return (
    <div className="space-y-2">
      <div className="text-sm font-medium">Accent color</div>
      <p className="text-muted-foreground text-xs">
        Default follows the color palette above. Pick a color to override it.
      </p>
      <div className="flex flex-wrap items-center gap-2.5">
        {ACCENT_COLORS.map(item => {
          const selected = accent === item.id
          const swatch = item.id === 'none' ? defaultSwatch : item.swatch
          return (
            <button
              key={item.id}
              type="button"
              title={item.label}
              aria-label={item.label}
              onClick={() => applyAccentColor(item.id)}
              onPointerEnter={() => previewAccentColor(item.id)}
              onPointerLeave={() => previewAccentColor(getStoredAccentColor())}
              onFocus={() => previewAccentColor(item.id)}
              onBlur={() => previewAccentColor(getStoredAccentColor())}
              className={cn(
                'flex size-7 shrink-0 items-center justify-center rounded-full ring-2 ring-offset-2 ring-offset-background transition-shadow',
                selected ? 'ring-foreground/70' : 'ring-transparent'
              )}
            >
              <span
                className={cn(
                  'flex size-6 items-center justify-center rounded-full',
                  item.id === 'none' && 'border-border border'
                )}
                style={{ backgroundColor: swatch }}
              >
                {selected ? (
                  <Check className="size-3.5 text-white drop-shadow" />
                ) : null}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function GeneralViewThemesSection({
  palette
}: {
  palette: ThemePaletteId
}) {
  const [liquidGlass, setLiquidGlass] = useState(() => getStoredLiquidGlass())
  const [macDesktop, setMacDesktop] = useState(() => showLiquidGlassOption())
  const [glassMaterial, setGlassMaterial] = useState(() => getStoredGlassMaterial())
  const [glassTintStrength, setGlassTintStrength] = useState(() =>
    getStoredGlassTintStrength()
  )
  const [accent, setAccent] = useState(() => getStoredAccentColor())
  const [tab, setTab] = useState<'presets' | 'custom'>(() =>
    getStoredPalette() === 'custom' ? 'custom' : 'presets'
  )
  const [customColors, setCustomColors] = useState(() => getStoredCustomTheme())

  useEffect(() => {
    if (palette !== 'custom') setTab('presets')
  }, [palette])

  useEffect(() => {
    setMacDesktop(showLiquidGlassOption())
    const onChange = (event: Event) => {
      setLiquidGlass(Boolean((event as CustomEvent<boolean>).detail))
    }
    const onMaterial = (event: Event) => {
      setGlassMaterial((event as CustomEvent<GlassMaterialId>).detail)
    }
    const onTintStrength = (event: Event) => {
      setGlassTintStrength((event as CustomEvent<number>).detail)
    }
    const onAccent = (event: Event) => {
      setAccent((event as CustomEvent<AccentColorId>).detail)
    }
    const onCustomTheme = (event: Event) => {
      setCustomColors((event as CustomEvent<CustomThemeColors>).detail)
    }
    window.addEventListener(LIQUID_GLASS_CHANGE_EVENT, onChange)
    window.addEventListener(GLASS_MATERIAL_CHANGE_EVENT, onMaterial)
    window.addEventListener(GLASS_TINT_STRENGTH_CHANGE_EVENT, onTintStrength)
    window.addEventListener(ACCENT_COLOR_CHANGE_EVENT, onAccent)
    window.addEventListener(CUSTOM_THEME_CHANGE_EVENT, onCustomTheme)
    return () => {
      window.removeEventListener(LIQUID_GLASS_CHANGE_EVENT, onChange)
      window.removeEventListener(GLASS_MATERIAL_CHANGE_EVENT, onMaterial)
      window.removeEventListener(GLASS_TINT_STRENGTH_CHANGE_EVENT, onTintStrength)
      window.removeEventListener(ACCENT_COLOR_CHANGE_EVENT, onAccent)
      window.removeEventListener(CUSTOM_THEME_CHANGE_EVENT, onCustomTheme)
    }
  }, [])

  return (
    <section className="space-y-4">
      <h3 className="text-base font-semibold">Color palette</h3>

      <div className="border-border inline-flex gap-1 rounded-lg border p-0.5">
        {(
          [
            { id: 'presets' as const, label: 'Presets' },
            { id: 'custom' as const, label: 'Custom theme' }
          ] as const
        ).map(item => (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              setTab(item.id)
              if (item.id === 'custom') applyPalette('custom')
            }}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              tab === item.id
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'presets' ? (
        <div className="space-y-3">
          <PaletteGrid palettes={THEME_PALETTES} palette={palette} />
          <button
            type="button"
            onClick={() => {
              resetAppearanceDefaults()
              setTab('presets')
            }}
            className="text-muted-foreground hover:text-foreground text-xs underline-offset-2 hover:underline"
          >
            Reset all to defaults
          </button>
        </div>
      ) : (
        <>
          <CustomThemeTab
            colors={customColors}
            onChange={next => {
              setCustomColors(next)
              applyCustomTheme(next)
            }}
          />
          <AccentColorRow
            accent={accent}
            defaultSwatch={resolvePaletteAccentSwatch(palette, customColors)}
          />
        </>
      )}

      {macDesktop ? (
        <div className="space-y-3 pt-2">
          <h4 className="text-sm font-semibold">Sidebar appearance</h4>
          <div className="grid gap-3 sm:grid-cols-2">
            {(
              [
                { id: 'glass' as const, name: 'Liquid glass', enabled: true },
                { id: 'solid' as const, name: 'Solid', enabled: false }
              ] as const
            ).map(item => {
              const selected = liquidGlass === item.enabled
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => applyLiquidGlass(item.enabled)}
                  className={cn(
                    'bg-card hover:bg-muted/40 relative flex items-center justify-between gap-2 rounded-xl border p-4 text-left transition-colors',
                    selected
                      ? 'border-primary ring-primary/20 ring-2'
                      : 'border-border'
                  )}
                >
                  <div className="text-sm font-semibold">{item.name}</div>
                  {selected ? (
                    <span className="bg-primary text-primary-foreground inline-flex size-6 shrink-0 items-center justify-center rounded-full">
                      <Check className="size-3.5" />
                    </span>
                  ) : null}
                </button>
              )
            })}
          </div>

          {liquidGlass ? (
            <div className="space-y-3 pt-1">
              <div className="border-border/70 flex items-center justify-between gap-3 rounded-xl border p-4">
                <div className="text-sm font-medium">Glass material</div>
                <select
                  value={glassMaterial}
                  onChange={event =>
                    applyGlassMaterial(event.target.value as GlassMaterialId)
                  }
                  className="border-border bg-card text-foreground focus-visible:ring-ring h-8 shrink-0 rounded-md border px-2 text-sm outline-none focus-visible:ring-1"
                >
                  {GLASS_MATERIALS.map(item => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="border-border/70 space-y-3 rounded-xl border p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium">Native tint strength</div>
                  <span className="text-muted-foreground w-10 shrink-0 text-right text-xs tabular-nums">
                    {glassTintStrength}%
                  </span>
                </div>
                <Slider
                  min={GLASS_TINT_STRENGTH_MIN}
                  max={GLASS_TINT_STRENGTH_MAX}
                  step={1}
                  value={[glassTintStrength]}
                  onValueChange={([next]) =>
                    applyGlassTintStrength(next ?? glassTintStrength)
                  }
                />
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
