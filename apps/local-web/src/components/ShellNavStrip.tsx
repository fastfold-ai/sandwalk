import { ArrowLeft, ArrowRight, PanelLeft } from 'lucide-react'
import type { ReactNode } from 'react'

import { DesktopDragRegion } from '@/components/DesktopDragRegion'
import { Button } from '@/components/ui/button'
import { useGlobalHistoryNav } from '@/hooks/useGlobalHistoryNav'
import { useMacDesktopOverlay } from '@/hooks/useMacDesktopOverlay'
import { cn } from '@/lib/utils'

type ShellNavControlsProps = {
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
  className?: string
}

/** Matches shell panel collapse duration — keep icon reveal in sync. */
export const SHELL_SIDEBAR_MOTION_MS = 220

/**
 * Sidebar toggle + global back/forward — shared by the sidebar strip and the
 * session header when the sidebar is collapsed (single chrome row with tabs).
 */
export function ShellNavControls({
  sidebarCollapsed,
  onToggleSidebar,
  className
}: ShellNavControlsProps) {
  const { canGoBack, canGoForward, goBack, goForward } = useGlobalHistoryNav()

  return (
    <div
      className={cn('flex shrink-0 items-center', className)}
      data-no-window-drag
    >
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="text-muted-foreground hover:text-foreground size-6 shrink-0"
        onClick={onToggleSidebar}
        aria-label={sidebarCollapsed ? 'Show sidebar' : 'Hide sidebar'}
        title={sidebarCollapsed ? 'Show sidebar' : 'Hide sidebar'}
      >
        <PanelLeft className="size-3" />
      </Button>
      <div className="ml-2 flex items-center gap-0.5">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-foreground size-6 shrink-0 disabled:opacity-35"
          disabled={!canGoBack}
          onClick={goBack}
          aria-label="Go back"
          title="Back"
        >
          <ArrowLeft className="size-3" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-foreground size-6 shrink-0 disabled:opacity-35"
          disabled={!canGoForward}
          onClick={goForward}
          aria-label="Go forward"
          title="Forward"
        >
          <ArrowRight className="size-3" />
        </Button>
      </div>
    </div>
  )
}

/**
 * Animated host for ShellNavControls — slides/fades instead of hard mount.
 * Keeps layout stable so tabs don't jump when chrome swaps sides.
 */
export function ShellNavControlsSlot({
  visible,
  sidebarCollapsed,
  onToggleSidebar,
  className
}: ShellNavControlsProps & { visible: boolean }) {
  return (
    <div
      className={cn(
        'sandwalk-shell-nav-slot overflow-hidden',
        visible
          ? 'mr-0.5 max-w-[8rem] opacity-100'
          : 'pointer-events-none mr-0 max-w-0 opacity-0',
        className
      )}
      aria-hidden={!visible}
    >
      <ShellNavControls
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={onToggleSidebar}
        className="whitespace-nowrap"
      />
    </div>
  )
}

type ShellNavStripProps = {
  /** When true, toggle expands the sidebar; otherwise it collapses. */
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
  /** Sidebar strip uses sidebar bg; main strip (collapsed) uses background. */
  surface?: 'sidebar' | 'main'
  /** Optional trailing chrome (e.g. session tabs) on the same row. */
  children?: ReactNode
}

/**
 * Shell chrome: traffic-light clearance (when needed), sidebar toggle,
 * global back/forward. Used in the sidebar when open, and on the main pane
 * when the sidebar is collapsed — same controls on every page.
 */
export function ShellNavStrip({
  sidebarCollapsed,
  onToggleSidebar,
  surface = 'sidebar',
  children
}: ShellNavStripProps) {
  const overlay = useMacDesktopOverlay()
  // Collapsed main strip owns traffic-light clearance; open sidebar strip too.
  const padForTrafficLights = overlay

  return (
    <DesktopDragRegion
      asTitleBar={overlay}
      className={cn(
        'sandwalk-shell-nav-strip relative z-20 flex w-full shrink-0 items-center pr-2',
        // Sidebar: transparent so glass reads as one column (not a title-bar band).
        surface === 'sidebar' ? 'bg-transparent' : 'bg-background',
        padForTrafficLights ? 'sandwalk-shell-nav-strip-mac' : 'pl-2'
      )}
    >
      <ShellNavControlsSlot
        visible
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={onToggleSidebar}
      />
      {children ?? <div className="min-h-7 min-w-0 flex-1 self-stretch" />}
    </DesktopDragRegion>
  )
}
