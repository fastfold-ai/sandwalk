import { useEffect, useRef } from 'react'

import { DesktopDragRegion } from '@/components/DesktopDragRegion'
import { startWindowDrag, toggleMaximize } from '@/lib/desktop'

export function AppShellTitleBar({ activeTitle }: { activeTitle: string }) {
  return (
    <DesktopDragRegion className="sandwalk-shell-nav-strip sandwalk-titlebar flex shrink-0 items-center gap-1 px-1.5 md:px-2">
      <span className="min-w-0 flex-1 truncate px-2 text-sm font-medium">
        {activeTitle}
      </span>
    </DesktopDragRegion>
  )
}

const INTERACTIVE_SELECTOR =
  'button, a, input, textarea, select, label, summary, [role="button"], [role="tab"], [role="menuitem"], [role="menuitemcheckbox"], [role="switch"], [role="checkbox"], [role="radio"], [role="combobox"], [role="option"], [data-no-window-drag], [data-radix-collection-item]'

function isInteractiveTarget(target: EventTarget | null) {
  return (
    target instanceof Element && Boolean(target.closest(INTERACTIVE_SELECTOR))
  )
}

function pointInStrip(strip: HTMLElement, x: number, y: number) {
  const rect = strip.getBoundingClientRect()
  return (
    x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom
  )
}

/**
 * Layout-neutral top drag zone for the main pane. Never intercepts hits —
 * listens in capture phase and only starts a window drag when the real target
 * under the pointer is non-interactive.
 */
export function AppShellMainDragStrip() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (event.button !== 0 || event.detail > 1) return
      const strip = ref.current
      if (!strip || !pointInStrip(strip, event.clientX, event.clientY)) return
      if (isInteractiveTarget(event.target)) return
      void startWindowDrag()
    }

    const onDoubleClick = (event: MouseEvent) => {
      const strip = ref.current
      if (!strip || !pointInStrip(strip, event.clientX, event.clientY)) return
      if (isInteractiveTarget(event.target)) return
      event.preventDefault()
      void toggleMaximize()
    }

    window.addEventListener('pointerdown', onPointerDown, true)
    window.addEventListener('dblclick', onDoubleClick, true)
    return () => {
      window.removeEventListener('pointerdown', onPointerDown, true)
      window.removeEventListener('dblclick', onDoubleClick, true)
    }
  }, [])

  return (
    <div
      ref={ref}
      className="sandwalk-main-drag-strip pointer-events-none absolute inset-x-0 top-0 z-10 w-full"
      aria-hidden
    />
  )
}
