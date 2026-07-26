import { DesktopDragRegion } from '@/components/DesktopDragRegion'
import { Button } from '@/components/ui/button'

export function ConnectionLimitBanner({
  runningCount,
  onDismiss
}: {
  runningCount: number
  onDismiss: () => void
}) {
  return (
    <div className="border-border bg-amber-500/10 text-amber-950 dark:text-amber-100 flex shrink-0 items-start gap-3 border-b px-3 py-2 text-xs">
      <div className="min-w-0 flex-1">
        <p className="font-medium">{runningCount} agents running at once</p>
        <p className="text-muted-foreground mt-0.5">
          Browsers allow about 6 live connections to the local API. With this
          many concurrent runs, opening files or switching chats can stall.
          Prefer finishing some runs before starting more.
        </p>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 shrink-0 px-2 text-xs"
        onClick={onDismiss}
      >
        Dismiss
      </Button>
    </div>
  )
}

export function AppShellTitleBar({ activeTitle }: { activeTitle: string }) {
  return (
    <DesktopDragRegion className="sandwalk-titlebar flex h-11 shrink-0 items-center gap-1 px-1.5 md:px-2">
      <span className="min-w-0 flex-1 truncate px-2 text-sm font-medium">
        {activeTitle}
      </span>
    </DesktopDragRegion>
  )
}

/**
 * Invisible absolute drag band on the main pane. Layout-neutral — does not
 * push content. Keep chrome (nav strip / session header) at a higher z-index
 * so buttons stay clickable.
 */
export function AppShellMainDragStrip() {
  return (
    <DesktopDragRegion
      asTitleBar
      className="sandwalk-main-drag-strip absolute inset-x-0 top-0 z-10 w-full"
      title="Drag to move window"
      aria-hidden
    />
  )
}
