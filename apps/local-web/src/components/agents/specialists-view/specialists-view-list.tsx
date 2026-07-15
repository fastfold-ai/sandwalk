import type { Specialist } from '@sandwalk/agent-ui-core'
import { Plus, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
import { SpecialistAvatar } from '@/components/agents/specialists-view/specialist-ui'
import { SpecialistToggle } from '@/components/agents/specialists-view/specialists-view-shared'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export function SpecialistsListView({
  specialists,
  loading,
  onOpenNew,
  onOpenEdit,
  onUpdate,
  onRefresh
}: {
  specialists: Specialist[]
  loading?: boolean
  onOpenNew: () => void
  onOpenEdit: (id: string) => void
  onUpdate: (
    id: string,
    input: {
      enabled?: boolean
    }
  ) => Promise<Specialist>
  onRefresh: () => Promise<void>
}) {
  const [listQuery, setListQuery] = useState('')
  const [togglePendingId, setTogglePendingId] = useState<string | null>(null)

  const filteredSpecialists = useMemo(() => {
    const needle = listQuery.trim().toLowerCase()
    if (!needle) return specialists
    return specialists.filter(item => {
      const haystack = [
        item.name,
        item.slug,
        item.description || '',
        item.skillNames.join(' '),
        item.mcpServerIds.join(' ')
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [listQuery, specialists])

  const toggleSpecialistEnabled = async (
    id: string,
    nextEnabled: boolean
  ) => {
    setTogglePendingId(id)
    try {
      await onUpdate(id, { enabled: nextEnabled })
      await onRefresh()
    } catch (cause) {
      toast.error(
        cause instanceof Error
          ? cause.message
          : 'Unable to update specialist'
      )
    } finally {
      setTogglePendingId(null)
    }
  }

  return (
    <div className="chat-scrollbar flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6">
        <div className="mb-0">
          <h2 className="text-2xl font-semibold">Specialists</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            Run profiles that scope skills, MCPs, and extra instructions for
            focused research sessions.
          </p>
        </div>

        <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
          <div className="relative min-w-[280px] max-w-3xl flex-1">
            <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
            <Input
              value={listQuery}
              onChange={event => setListQuery(event.target.value)}
              placeholder="Search specialists, descriptions..."
              className="border-border/70 bg-background/70 h-11 pl-10"
            />
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-10 shrink-0"
            onClick={onOpenNew}
          >
            <Plus className="size-3.5" />
            New specialist
          </Button>
        </div>

        {loading ? (
          <ListRowsSkeleton />
        ) : specialists.length === 0 ? (
          <p className="text-muted-foreground py-16 text-center text-sm">
            No specialists yet
          </p>
        ) : filteredSpecialists.length === 0 ? (
          <p className="text-muted-foreground py-8 text-center text-sm">
            No specialists match “{listQuery.trim()}”.
          </p>
        ) : (
          <div className="divide-border/60 divide-y">
            {filteredSpecialists.map(item => {
              const isEnabled = item.enabled !== false
              return (
                <div
                  key={item.id}
                  className={cn(
                    'hover:bg-muted/40 -mx-2 flex w-[calc(100%+1rem)] items-start gap-3 rounded-lg px-2 py-3.5 transition-colors',
                    !isEnabled && 'opacity-60'
                  )}
                >
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 items-start gap-3 text-left"
                    onClick={() => onOpenEdit(item.id)}
                  >
                    <SpecialistAvatar color={item.color} icon={item.icon} />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline gap-2">
                        <span className="truncate text-sm font-medium">
                          {item.name}
                        </span>
                        <span className="text-muted-foreground shrink-0 text-xs">
                          {item.slug}
                        </span>
                        {!isEnabled ? (
                          <span className="text-muted-foreground shrink-0 text-[11px]">
                            Off
                          </span>
                        ) : null}
                      </span>
                      <span className="text-muted-foreground mt-0.5 block line-clamp-1 text-sm">
                        {item.description || 'No description'}
                      </span>
        <span className="text-muted-foreground mt-1.5 block text-xs">
                        {item.skillNames.length} skill
                        {item.skillNames.length === 1 ? '' : 's'}
                        <span className="mx-1.5 opacity-40">·</span>
                        {(item.toolNames?.length || 0)} tool
                        {(item.toolNames?.length || 0) === 1 ? '' : 's'}
                        <span className="mx-1.5 opacity-40">·</span>
                        {(item.mcpServerIds?.length || 0) +
                          (item.mcpCatalogIds?.length || 0)}{' '}
                        MCP
                        {(item.mcpServerIds?.length || 0) +
                          (item.mcpCatalogIds?.length || 0) ===
                        1
                          ? ''
                          : 's'}
                      </span>
                    </span>
                  </button>
                  <div className="flex shrink-0 items-center pt-1">
                    <SpecialistToggle
                      enabled={isEnabled}
                      pending={togglePendingId === item.id}
                      label={`${isEnabled ? 'Disable' : 'Enable'} ${item.name}`}
                      onToggle={() =>
                        void toggleSpecialistEnabled(item.id, !isEnabled)
                      }
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
