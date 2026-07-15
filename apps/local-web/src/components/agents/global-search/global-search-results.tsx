import { Icon } from '@iconify/react'
import type { AgentSession } from '@sandwalk/agent-ui-core'
import {
  AtSign,
  Hash,
  MessageSquare,
  Zap
} from 'lucide-react'

import {
  CommandEmpty,
  CommandGroup,
  CommandItem
} from '@/components/ui/command'
import { getFileIcon } from '@/lib/file-icons'
import { cn, relativeTime } from '@/lib/utils'

import {
  DASHBOARD_COMMANDS,
  type IndexedArtifact
} from './global-search-utils'

export function GlobalSearchResults({
  indexing,
  showArtifacts,
  showSessions,
  showCommands,
  filteredArtifacts,
  filteredSessions,
  onOpenArtifact,
  onMentionArtifact,
  onOpenSession,
  onCreateSession,
  onNavigate,
  onClose
}: {
  indexing: boolean
  showArtifacts: boolean
  showSessions: boolean
  showCommands: boolean
  filteredArtifacts: IndexedArtifact[]
  filteredSessions: AgentSession[]
  onOpenArtifact: (sessionId: string, path: string) => void
  onMentionArtifact: (sessionId: string, path: string) => void
  onOpenSession: (sessionId: string) => void
  onCreateSession: () => void
  onNavigate: (path: string) => void
  onClose: () => void
}) {
  return (
    <>
      <CommandEmpty>
        {indexing ? 'Indexing files…' : 'No results found.'}
      </CommandEmpty>

      {showArtifacts && filteredArtifacts.length > 0 ? (
        <CommandGroup heading="Recent artifacts">
          {filteredArtifacts.map(item => (
            <CommandItem
              key={`artifact:${item.sessionId}:${item.path}`}
              value={`artifact ${item.sessionId} ${item.path} ${item.name}`}
              onSelect={() => {
                onOpenArtifact(item.sessionId, item.path)
                onClose()
              }}
              className="group gap-2.5 py-2"
            >
              <Icon
                icon={getFileIcon(item.name)}
                className="size-4 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{item.name}</div>
                <div className="text-muted-foreground truncate text-[11px]">
                  {item.sessionTitle}
                  {item.mtime ? ` · ${relativeTime(item.mtime)}` : ''}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-data-[selected=true]:opacity-100">
                <button
                  type="button"
                  className="hover:bg-background/60 rounded p-1"
                  title="Mention in chat"
                  onClick={event => {
                    event.preventDefault()
                    event.stopPropagation()
                    onMentionArtifact(item.sessionId, item.path)
                    onClose()
                  }}
                >
                  <AtSign className="size-3.5" />
                </button>
              </div>
            </CommandItem>
          ))}
        </CommandGroup>
      ) : null}

      {showSessions && filteredSessions.length > 0 ? (
        <CommandGroup heading="Recent sessions">
          {filteredSessions.map(session => (
            <CommandItem
              key={`session:${session.id}`}
              value={`session ${session.id} ${session.title}`}
              onSelect={() => {
                onOpenSession(session.id)
                onClose()
              }}
              className="gap-2.5 py-2"
            >
              <MessageSquare className="text-muted-foreground size-4 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">
                  {session.title}
                </div>
                <div className="text-muted-foreground truncate text-[11px]">
                  {relativeTime(session.lastMessageAt || session.updatedAt)}
                </div>
              </div>
              <span className="text-primary shrink-0 text-[11px] font-medium">
                Session
              </span>
            </CommandItem>
          ))}
        </CommandGroup>
      ) : null}

      {showCommands ? (
        <CommandGroup heading="Commands">
          <CommandItem
            value="command new session"
            onSelect={() => {
              onCreateSession()
              onClose()
            }}
            className="gap-2.5 py-2"
          >
            <Zap className="text-muted-foreground size-4 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">New session</div>
            </div>
            <span className="text-muted-foreground text-[11px]">⌘N</span>
          </CommandItem>
          {DASHBOARD_COMMANDS.map(command => {
            const IconComponent = command.icon
            return (
              <CommandItem
                key={command.id}
                value={command.value}
                onSelect={() => {
                  onNavigate(command.path)
                  onClose()
                }}
                className="gap-2.5 py-2"
              >
                <IconComponent className="text-muted-foreground size-4 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{command.label}</div>
                </div>
              </CommandItem>
            )
          })}
        </CommandGroup>
      ) : null}
    </>
  )
}

export function GlobalSearchFooter({
  scope,
  onApplyScope
}: {
  scope: 'all' | 'artifacts' | 'sessions'
  onApplyScope: (scope: 'artifacts' | 'sessions') => void
}) {
  return (
    <div className="text-muted-foreground flex items-center justify-between gap-3 border-t px-3 py-2 text-[11px]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span>↑↓ navigate</span>
        <span>↵ open</span>
        {scope === 'artifacts' || scope === 'all' ? (
          <span>@ mention</span>
        ) : null}
        <span>esc close</span>
        {scope !== 'all' ? <span>⌫ clear filter</span> : null}
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        {scope !== 'artifacts' ? (
          <button
            type="button"
            onClick={() => onApplyScope('artifacts')}
            className={cn(
              'inline-flex items-center gap-1 rounded-full border px-2 py-0.5',
              scope === 'all' && 'hover:bg-muted/60'
            )}
          >
            <AtSign className="size-3" />
            artifacts
          </button>
        ) : null}
        {scope !== 'sessions' ? (
          <button
            type="button"
            onClick={() => onApplyScope('sessions')}
            className={cn(
              'inline-flex items-center gap-1 rounded-full border px-2 py-0.5',
              scope === 'all' && 'hover:bg-muted/60'
            )}
          >
            <Hash className="size-3" />
            sessions
          </button>
        ) : null}
      </div>
    </div>
  )
}
