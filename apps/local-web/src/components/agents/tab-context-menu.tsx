import { Ban } from 'lucide-react'
import { type ReactNode, useEffect, useRef } from 'react'

import { cn } from '@/lib/utils'

/** Soft pastel dots marking colored tabs (Cursor-style). */
export const TAB_INLINE_COLORS: { name: string; value: string }[] = [
  { name: 'Pink', value: '#F5A9C5' },
  { name: 'Green', value: '#86D4A8' },
  { name: 'Yellow', value: '#D4C878' },
  { name: 'Blue', value: '#8BB8F5' },
  { name: 'Purple', value: '#B5A4F5' },
  { name: 'Teal', value: '#76C0A7' }
]

export function TabContextMenuShell({
  x,
  y,
  onClose,
  children
}: {
  x: number
  y: number
  onClose: () => void
  children: ReactNode
}) {
  const menuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (menuRef.current?.contains(event.target as Node)) return
      onClose()
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    const onScroll = () => onClose()
    window.addEventListener('click', close, true)
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      window.removeEventListener('click', close, true)
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [onClose])

  const left = Math.min(x, window.innerWidth - 220)
  const top = Math.min(y, window.innerHeight - 220)

  return (
    <div
      ref={menuRef}
      className="bg-popover text-popover-foreground fixed z-50 min-w-[11.5rem] rounded-md border p-1 shadow-md"
      style={{ left, top }}
      role="menu"
      onClick={event => event.stopPropagation()}
    >
      {children}
    </div>
  )
}

export function TabContextItem({
  icon,
  label,
  onClick,
  disabled,
  destructive,
  trailing
}: {
  icon: ReactNode
  label: string
  onClick: () => void
  disabled?: boolean
  destructive?: boolean
  trailing?: ReactNode
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      className={cn(
        'flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm',
        destructive
          ? 'text-red-600 hover:bg-red-50 disabled:opacity-40 dark:hover:bg-red-950/20'
          : 'hover:bg-muted disabled:opacity-40',
        disabled && 'pointer-events-none'
      )}
      onMouseDown={event => {
        // Keep focus from jumping (e.g. into xterm) before inline rename mounts.
        event.preventDefault()
      }}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onClick()
      }}
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {trailing}
    </button>
  )
}

export function TabContextSeparator() {
  return <div className="bg-border my-1 h-px" />
}

/** Inline swatch row: none + named colors (no submenu). */
export function TabInlineColorRow({
  value,
  onSelect,
  onClear
}: {
  value?: string | null
  onSelect: (color: string) => void
  onClear: () => void
}) {
  return (
    <div
      className="flex items-center gap-1.5 px-2 py-1.5"
      role="group"
      aria-label="Tab color"
    >
      <button
        type="button"
        title="None"
        aria-label="Clear color"
        className={cn(
          'text-muted-foreground hover:bg-muted inline-flex size-5 items-center justify-center rounded-full border border-dashed',
          !value && 'ring-primary ring-2 ring-offset-1 ring-offset-popover'
        )}
        onClick={event => {
          event.preventDefault()
          event.stopPropagation()
          onClear()
        }}
      >
        <Ban className="size-3.5" strokeWidth={1.75} />
      </button>
      {TAB_INLINE_COLORS.map(swatch => {
        const selected = value === swatch.value
        return (
          <button
            key={swatch.value}
            type="button"
            title={swatch.name}
            aria-label={swatch.name}
            aria-pressed={selected}
            className={cn(
              'size-5 shrink-0 rounded-full border border-black/5 transition-shadow',
              selected
                ? 'ring-primary ring-2 ring-offset-1 ring-offset-popover'
                : 'hover:ring-muted-foreground/40 hover:ring-2 hover:ring-offset-1 hover:ring-offset-popover'
            )}
            style={{ backgroundColor: swatch.value }}
            onClick={event => {
              event.preventDefault()
              event.stopPropagation()
              onSelect(swatch.value)
            }}
          />
        )
      })}
    </div>
  )
}
