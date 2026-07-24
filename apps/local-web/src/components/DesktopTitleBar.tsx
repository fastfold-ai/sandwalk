import { DesktopDragRegion } from '@/components/DesktopDragRegion'
import { useMacDesktopOverlay } from '@/hooks/useMacDesktopOverlay'

/**
 * Full-width macOS overlay title bar — hold-drag anywhere here to move the window
 * (Cursor / native Mac app pattern). Traffic lights sit in the left inset.
 */
export function DesktopTitleBar() {
  const overlay = useMacDesktopOverlay()
  if (!overlay) return null

  return (
    <DesktopDragRegion
      asTitleBar
      className="bg-background border-border/50 flex h-11 w-full shrink-0 items-center border-b pl-[78px]"
      title="Drag to move window"
    >
      {/* Empty fill — hold-click and drag anywhere here to move the window. */}
      <div className="h-full min-w-0 flex-1" />
    </DesktopDragRegion>
  )
}
