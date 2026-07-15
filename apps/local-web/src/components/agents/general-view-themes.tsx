import { Check } from 'lucide-react'

import {
  applyPalette,
  getStoredPalette,
  previewPalette,
  THEME_PALETTES,
  type ThemePaletteId
} from '@/lib/theme'
import { cn } from '@/lib/utils'

export function GeneralViewThemesSection({
  palette
}: {
  palette: ThemePaletteId
}) {
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">Themes</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          Color palettes for light and dark mode. Mode and palette also live
          in the user menu under Theme.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {THEME_PALETTES.map(item => {
          const selected = palette === item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => applyPalette(item.id)}
              onPointerEnter={() => previewPalette(item.id)}
              onPointerLeave={() => previewPalette(getStoredPalette())}
              onFocus={() => previewPalette(item.id)}
              onBlur={() => previewPalette(getStoredPalette())}
              className={cn(
                'bg-card hover:bg-muted/40 relative flex flex-col gap-3 rounded-xl border p-4 text-left transition-colors',
                selected
                  ? 'border-primary ring-primary/20 ring-2'
                  : 'border-border'
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-semibold">{item.name}</div>
                  <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
                    {item.description}
                  </p>
                </div>
                {selected ? (
                  <span className="bg-primary text-primary-foreground inline-flex size-6 shrink-0 items-center justify-center rounded-full">
                    <Check className="size-3.5" />
                  </span>
                ) : null}
              </div>
              <div className="flex items-center gap-1.5">
                {item.swatches.map(color => (
                  <span
                    key={color}
                    className="border-border size-7 rounded-md border shadow-sm"
                    style={{ backgroundColor: color }}
                    title={color}
                  />
                ))}
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}
