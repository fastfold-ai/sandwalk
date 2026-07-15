import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession, WorkspaceFile } from '@sandwalk/agent-ui-core'
import { Command as CommandPrimitive } from 'cmdk'
import { Search, X } from 'lucide-react'

import {
  CommandDialog,
  CommandList
} from '@/components/ui/command'

import {
  GlobalSearchFooter,
  GlobalSearchResults
} from './global-search/global-search-results'
import { placeholderFor, scopeLabel } from './global-search/global-search-utils'
import { useGlobalSearchState } from './global-search/use-global-search-state'

export type { IndexedArtifact, SearchScope } from './global-search/global-search-utils'
export { useGlobalSearchHotkey } from './global-search/use-global-search-hotkey'

type GlobalSearchDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  client: LocalAgentClient
  sessions: AgentSession[]
  currentSessionId: string | null
  currentSessionTitle?: string | null
  workspaceFiles: WorkspaceFile[]
  onOpenSession: (sessionId: string) => void
  onOpenArtifact: (sessionId: string, path: string) => void
  onMentionArtifact: (sessionId: string, path: string) => void
  onCreateSession: () => void
  onNavigate: (path: string) => void
}

export function GlobalSearchDialog({
  open,
  onOpenChange,
  client,
  sessions,
  currentSessionId,
  currentSessionTitle,
  workspaceFiles,
  onOpenSession,
  onOpenArtifact,
  onMentionArtifact,
  onCreateSession,
  onNavigate
}: GlobalSearchDialogProps) {
  const search = useGlobalSearchState({
    open,
    onOpenChange,
    client,
    sessions,
    currentSessionId,
    currentSessionTitle,
    workspaceFiles
  })

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      contentClassName="top-[18%] translate-y-0 max-w-2xl gap-0 rounded-xl border-border/70 bg-popover shadow-2xl"
      overlayClassName="bg-black/50 backdrop-blur-[1px]"
      commandProps={{
        shouldFilter: false,
        className: 'rounded-xl'
      }}
    >
      <div
        className="flex items-center gap-2 border-b px-3 py-2.5"
        cmdk-input-wrapper=""
      >
        <Search className="text-muted-foreground size-4 shrink-0 opacity-70" />
        {search.scope !== 'all' ? (
          <button
            type="button"
            onClick={search.clearScope}
            className="bg-muted text-foreground inline-flex h-6 shrink-0 items-center gap-1 rounded-full px-2 text-xs"
          >
            {scopeLabel(search.scope)}
            <X className="size-3 opacity-70" />
          </button>
        ) : null}
        <CommandPrimitive.Input
          ref={search.inputRef}
          value={search.query}
          onValueChange={search.handleQueryChange}
          onKeyDown={search.handleInputKeyDown}
          placeholder={placeholderFor(search.scope)}
          className="placeholder:text-muted-foreground h-8 min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        {currentSessionTitle ? (
          <span className="text-muted-foreground/70 max-w-[7rem] truncate rounded-md border px-1.5 py-0.5 text-[10px]">
            {currentSessionTitle}
          </span>
        ) : null}
      </div>

      <CommandList className="chat-scrollbar max-h-[420px] overflow-y-auto px-1 py-1">
        <GlobalSearchResults
          indexing={search.indexing}
          showArtifacts={search.showArtifacts}
          showSessions={search.showSessions}
          showCommands={search.showCommands}
          filteredArtifacts={search.filteredArtifacts}
          filteredSessions={search.filteredSessions}
          onOpenArtifact={onOpenArtifact}
          onMentionArtifact={onMentionArtifact}
          onOpenSession={onOpenSession}
          onCreateSession={onCreateSession}
          onNavigate={onNavigate}
          onClose={search.close}
        />
      </CommandList>

      <GlobalSearchFooter
        scope={search.scope}
        onApplyScope={search.applyScopeFromKey}
      />
    </CommandDialog>
  )
}
