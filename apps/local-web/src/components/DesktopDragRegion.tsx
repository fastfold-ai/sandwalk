import type {
  HTMLAttributes,
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent
} from 'react'

import { startWindowDrag, toggleMaximize } from '@/lib/desktop'
import { cn } from '@/lib/utils'

type Props = HTMLAttributes<HTMLDivElement> & {
  /** When true, children stay interactive (no-drag). */
  asTitleBar?: boolean
}

function isInteractiveTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  return Boolean(
    target.closest(
      'button, a, input, textarea, select, [role="button"], [data-no-window-drag]'
    )
  )
}

/**
 * Native window drag surface for macOS Tauri overlay windows.
 * - Hold-drag moves the window
 * - Double-click toggles maximize (native title-bar behavior)
 */
export function DesktopDragRegion({
  className,
  asTitleBar = false,
  onPointerDown,
  onDoubleClick,
  children,
  ...rest
}: Props) {
  const beginDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    onPointerDown?.(event)
    if (event.defaultPrevented || event.button !== 0) return
    // Second click of a double-click — let onDoubleClick handle maximize.
    if (event.detail > 1) return
    if (isInteractiveTarget(event.target)) return
    void startWindowDrag()
  }

  const onZoom = (event: ReactMouseEvent<HTMLDivElement>) => {
    onDoubleClick?.(event)
    if (event.defaultPrevented) return
    if (isInteractiveTarget(event.target)) return
    event.preventDefault()
    void toggleMaximize()
  }

  return (
    <div
      {...rest}
      data-tauri-drag-region
      className={cn(
        'sandwalk-drag-region select-none',
        asTitleBar && 'sandwalk-desktop-titlebar',
        className
      )}
      onPointerDown={beginDrag}
      onDoubleClick={onZoom}
    >
      {children}
    </div>
  )
}
