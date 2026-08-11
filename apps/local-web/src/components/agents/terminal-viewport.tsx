import type { PtySessionInfo } from '@sandwalk/agent-ui-core'
import { Plus } from 'lucide-react'
import type { RefObject } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function TerminalViewport({
  booting,
  status,
  tabs,
  activeId,
  hostsRef,
  onCreateTab
}: {
  booting: boolean
  status: string | null
  tabs: PtySessionInfo[]
  activeId: string | null
  hostsRef: RefObject<Record<string, HTMLDivElement | null>>
  onCreateTab: () => void
}) {
  return (
    <div className="relative min-h-0 flex-1">
      {booting ? (
        <div className="text-muted-foreground absolute inset-0 flex items-center justify-center text-xs">
          Starting terminal…
        </div>
      ) : status && tabs.length === 0 ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
          <p className="text-destructive text-xs">{status}</p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={onCreateTab}
          >
            Retry
          </Button>
        </div>
      ) : tabs.length === 0 ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
          <p className="text-muted-foreground text-xs">No terminals open</p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={onCreateTab}
          >
            <Plus className="mr-1 size-3.5" />
            New terminal
          </Button>
        </div>
      ) : (
        tabs.map(tab => (
          <div
            key={tab.id}
            className={cn(
              'absolute inset-0 overflow-hidden px-2 pb-2 pt-0.5 [&_.xterm]:h-full [&_.xterm-viewport]:!overflow-auto',
              activeId === tab.id ? 'block' : 'hidden'
            )}
            ref={node => {
              hostsRef.current[tab.id] = node
            }}
          />
        ))
      )}
    </div>
  )
}
