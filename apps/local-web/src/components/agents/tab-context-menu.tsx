import { Ban, ChevronRight } from 'lucide-react'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

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
    // X4.4-hotfix (bug A/C): antes había un listener de `scroll` con
    // capture:true que cerraba el menú en cualquier scroll de cualquier
    // elemento. Cuando el agente hacía streaming, el chat auto-scrollea
    // para seguir el output → el menú context se cerraba solo cada vez
    // que el user intentaba abrirlo mientras el agente escribía.
    // Los menús context estándar no se cierran por scroll de contenido;
    // se cierran por click fuera o Escape. Suficiente.
    window.addEventListener('click', close, true)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('click', close, true)
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  const left = Math.min(x, window.innerWidth - 220)
  const top = Math.min(y, window.innerHeight - 220)

  /*
   * Portal to document.body so the menu escapes the tab-strip's stacking
   * context (created by `.relative.z-[1]` in SessionTabs). Otherwise the
   * tab ::before dividers (z:3) and close buttons (z:2) paint on top of
   * the menu's border and produce a black hairline artifact along the edge.
   */
  return createPortal(
    <div
      ref={menuRef}
      className="bg-popover text-popover-foreground fixed z-50 min-w-[11.5rem] rounded-md border p-1 shadow-md"
      style={{ left, top }}
      role="menu"
      onClick={event => event.stopPropagation()}
    >
      {children}
    </div>,
    document.body
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
        'flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-xs',
        '[&_svg]:size-3',
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

/** Flyout opened by hovering a row. Used for Split down / Split right. */
export function TabContextSubmenu({
  icon,
  label,
  trailing,
  children
}: {
  icon: ReactNode
  label: string
  trailing?: ReactNode
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <div
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <div className="hover:bg-muted flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-xs [&_svg]:size-3.5">
        {icon}
        <span className="min-w-0 flex-1 truncate">{label}</span>
        {trailing}
        <ChevronRight className="size-3 shrink-0 opacity-60" />
      </div>
      {open ? (
        <div className="bg-popover text-popover-foreground absolute top-0 left-full z-50 ml-1 min-w-[11rem] rounded-md border p-1 shadow-md">
          {children}
        </div>
      ) : null}
    </div>
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
      className="flex items-center gap-1 px-2 py-1"
      role="group"
      aria-label="Tab color"
    >
      <button
        type="button"
        title="None"
        aria-label="Clear color"
        className={cn(
          'text-muted-foreground hover:bg-muted inline-flex size-4 items-center justify-center rounded-full border border-dashed',
          !value && 'ring-primary ring-2 ring-offset-1 ring-offset-popover'
        )}
        onClick={event => {
          event.preventDefault()
          event.stopPropagation()
          onClear()
        }}
      >
        <Ban className="size-3" strokeWidth={1.75} />
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
              'size-4 shrink-0 rounded-full border border-black/5 transition-shadow',
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
