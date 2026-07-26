import { DesktopDragRegion } from '@/components/DesktopDragRegion'
import { useMacDesktopOverlay } from '@/hooks/useMacDesktopOverlay'

/**
 * Full-width macOS overlay title bar for gate/login screens (no sidebar split).
 * The main AppShell does not use this — traffic-light clearance lives in
 * `.sandwalk-sidebar-chrome` so the sidebar|main divider can run edge-to-edge.
 */
export function DesktopTitleBar() {
  const overlay = useMacDesktopOverlay()
  if (!overlay) return null

  return (
    <DesktopDragRegion
      asTitleBar
      className="bg-background flex h-11 w-full shrink-0 items-center pl-[78px]"
      title="Drag to move window"
    >
      {/* Empty fill — hold-click and drag anywhere here to move the window. */}
      <div className="h-full min-w-0 flex-1" />
    </DesktopDragRegion>
  )
}
