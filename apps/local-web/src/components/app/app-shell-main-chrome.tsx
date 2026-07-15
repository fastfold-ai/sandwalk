import { PanelLeft } from 'lucide-react'

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

export function AppShellTitleBar({
  sidebarCollapsed,
  setSidebarCollapsed,
  activeTitle
}: {
  sidebarCollapsed: boolean
  setSidebarCollapsed: (value: boolean | ((current: boolean) => boolean)) => void
  activeTitle: string
}) {
  return (
    <div className="flex h-10 shrink-0 items-center gap-1 border-b px-1.5 md:px-2">
      {sidebarCollapsed ? (
        <Button
          variant="ghost"
          size="icon"
          className="size-8 shrink-0"
          onClick={() => setSidebarCollapsed(false)}
          aria-label="Show sidebar"
        >
          <PanelLeft className="size-4" />
        </Button>
      ) : null}
      <span className="min-w-0 flex-1 truncate px-2 text-sm font-medium">
        {activeTitle}
      </span>
    </div>
  )
}

export function AppShellFloatingSidebarToggle({
  setSidebarCollapsed
}: {
  setSidebarCollapsed: (value: boolean | ((current: boolean) => boolean)) => void
}) {
  return (
    <div className="absolute left-2 top-2 z-20">
      <Button
        variant="ghost"
        size="icon"
        className="size-8 shrink-0"
        onClick={() => setSidebarCollapsed(false)}
        aria-label="Show sidebar"
      >
        <PanelLeft className="size-4" />
      </Button>
    </div>
  )
}
