import { useState } from 'react'

import { cn } from '@/lib/utils'

/**
 * Rearrange the open panes into equal rows. `cols` is panes across,
 * `rows` is how many bands that makes for the current count.
 */
export function GridArrangeControl({
  count,
  onArrange
}: {
  count: number
  onArrange: (rows: number, cols: number) => void
}) {
  const [open, setOpen] = useState(false)
  if (count < 2) return null

  const choices = [
    { cols: count, label: 'One row' },
    { cols: 2, label: '2 across' },
    { cols: 3, label: '3 across' },
    { cols: 4, label: '4 across' },
    { cols: 1, label: 'One column' }
  ].filter((choice, index, all) => all.findIndex(item => item.cols === choice.cols) === index)

  return (
    <div className="pointer-events-none absolute top-3 left-1/2 z-30 -translate-x-1/2">
      <div className="pointer-events-auto">
        <button
          type="button"
          className="bg-background/90 text-muted-foreground hover:text-foreground rounded-full border px-2.5 py-1 text-[11px] shadow-sm backdrop-blur"
          aria-expanded={open}
          aria-label="Arrange grid"
          onClick={() => setOpen(current => !current)}
        >
          Arrange
        </button>
        {open ? (
          <div className="bg-popover mt-1 flex gap-1 rounded-lg border p-1 shadow-md">
            {choices.map(choice => {
              const cols = Math.max(1, Math.min(choice.cols, count))
              const rows = Math.ceil(count / cols)
              return (
                <button
                  key={choice.label}
                  type="button"
                  className={cn(
                    'hover:bg-accent rounded-md px-2 py-1 text-[11px] whitespace-nowrap'
                  )}
                  onClick={() => {
                    onArrange(rows, cols)
                    setOpen(false)
                  }}
                >
                  {choice.label}
                  <span className="text-muted-foreground block text-[10px]">
                    {cols}×{rows}
                  </span>
                </button>
              )
            })}
          </div>
        ) : null}
      </div>
    </div>
  )
}
