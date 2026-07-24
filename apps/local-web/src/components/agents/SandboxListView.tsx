import { ArrowRight, Monitor } from 'lucide-react'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

const MODAL_ICON = INTEGRATION_ICONS.modal

type SandboxItem = {
  id: 'local' | 'modal'
  name: string
  description: string
  badge?: string
}

const ITEMS: SandboxItem[] = [
  {
    id: 'local',
    name: 'Local Sandbox',
    description:
      'Python environment on this machine. View interpreter path, disk usage, and manage packages for skills and tools.',
    badge: 'Default'
  },
  {
    id: 'modal',
    name: 'Modal Sandbox',
    description:
      'Cloud compute on Modal. Configure credentials, CPU/GPU profiles, base images, and default pip packages.',
  }
]

export function SandboxListView({
  onOpen
}: {
  onOpen: (id: 'local' | 'modal') => void
}) {
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl space-y-8 p-4 md:p-6">
        <div>
          <h2 className="text-2xl font-semibold">Sandbox</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Choose a sandbox to configure. Chats default to Local Sandbox; enable
            Modal per chat in the composer.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {ITEMS.map(item => (
            <button
              key={item.id}
              type="button"
              onClick={() => onOpen(item.id)}
              className={cn(
                'bg-background/60 hover:bg-muted/40 group flex h-full flex-col rounded-lg border border-border/60 p-4 text-left transition-colors'
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2.5">
                  {item.id === 'modal' && MODAL_ICON ? (
                    <img
                      src={MODAL_ICON.src}
                      alt=""
                      className="size-7 shrink-0 rounded object-contain"
                    />
                  ) : (
                    <span className="bg-muted text-muted-foreground grid size-7 shrink-0 place-items-center rounded">
                      <Monitor className="size-4" />
                    </span>
                  )}
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate text-sm font-medium">
                        {item.name}
                      </span>
                      {item.badge ? (
                        <span className="bg-muted text-muted-foreground rounded px-1.5 py-0.5 text-[10px] font-medium">
                          {item.badge}
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>
                <ArrowRight className="text-muted-foreground size-4 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
              </div>
              <p className="text-muted-foreground mt-2 line-clamp-3 text-sm leading-relaxed">
                {item.description}
              </p>
            </button>
          ))}
        </div>
      </div>
    </ScrollArea>
  )
}
