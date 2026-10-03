import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  SessionGroup
} from '@sandwalk/agent-ui-core'
import { ArrowLeft, MessageSquare, Plus, SquareTerminal, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { SplitChatPickerPanel } from '@/components/agents/SplitChatPickerPanel'
import { cn } from '@/lib/utils'

/**
 * Two-step picker that replaces the empty pane when the user triggers
 * "Split right/left/up/down" (FAS-107).
 *
 * Step 1 — What to add?
 *   Compact tiles: Terminal | Agent.
 *
 * Step 2 (only when step 1 = "New agent chat") — Which chat?
 *   Existing `SplitChatPickerPanel` behind a "← Back" button, with
 *   "Start new chat" separated by a divider at the bottom.
 *
 * Animations use fade + slide (~180ms ease-out) between the two steps
 * so the transition reads as one movement instead of a hard cut.
 */

export type SplitPickerProps = {
  client: LocalAgentClient
  sourceChatId: string
  activeProjectId: string | null
  projects: AgentProject[]
  allTabGroups: SessionGroup[]
  cachedSessions: AgentSession[]
  /** Chosen: existing chat (called with its id). */
  onPickChat: (chatId: string) => void
  /** Chosen: create a new chat from scratch. */
  onPickNewChat: () => void
  /** Chosen: create a new terminal (auto-named "Terminal N"). */
  onPickTerminal: () => void
  /** X or Esc — cancels the split. */
  onCancel: () => void
}

type Step = 'type' | 'chat'

export function SplitPicker(props: SplitPickerProps) {
  const [step, setStep] = useState<Step>('type')
  const [entering, setEntering] = useState(true)

  useEffect(() => {
    // Kick off the enter animation on first mount.
    const raf = requestAnimationFrame(() => setEntering(false))
    return () => cancelAnimationFrame(raf)
  }, [])

  return (
    <div className="bg-background border-border/50 relative flex h-full min-w-0 flex-col overflow-hidden rounded-lg border">
      <button
        type="button"
        onClick={props.onCancel}
        aria-label="Cancel"
        className="text-muted-foreground hover:text-foreground hover:bg-muted absolute right-2 top-2 z-20 inline-flex size-7 items-center justify-center rounded-md"
      >
        <X className="size-4" />
      </button>
      <div
        className={cn(
          'flex h-full min-h-0 min-w-0 flex-col overflow-hidden transition-[opacity,transform] duration-[180ms] ease-out',
          entering ? 'translate-y-1 opacity-0' : 'translate-y-0 opacity-100'
        )}
      >
        {step === 'type' ? (
          <TypeStep
            onPickTerminal={props.onPickTerminal}
            onGoToChatStep={() => setStep('chat')}
          />
        ) : (
          <ChatStep
            client={props.client}
            sourceChatId={props.sourceChatId}
            activeProjectId={props.activeProjectId}
            projects={props.projects}
            allTabGroups={props.allTabGroups}
            cachedSessions={props.cachedSessions}
            onBack={() => setStep('type')}
            onPickChat={props.onPickChat}
            onPickNewChat={props.onPickNewChat}
          />
        )}
      </div>
    </div>
  )
}

function TypeStep({
  onPickTerminal,
  onGoToChatStep
}: {
  onPickTerminal: () => void
  onGoToChatStep: () => void
}) {
  return (
    <div className="flex h-full min-h-0 min-w-0 items-center justify-center overflow-hidden p-6">
      <div className="grid grid-cols-2 gap-3">
        <TypeCard
          label="Terminal"
          icon={<SquareTerminal className="size-4" strokeWidth={1.75} />}
          onClick={onPickTerminal}
        />
        <TypeCard
          label="Agent"
          icon={<MessageSquare className="size-4" strokeWidth={1.75} />}
          onClick={onGoToChatStep}
        />
      </div>
    </div>
  )
}

function TypeCard({
  label,
  icon,
  onClick
}: {
  label: string
  icon: React.ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'text-muted-foreground hover:bg-muted hover:text-foreground flex size-[5.5rem] flex-col items-center justify-center gap-2 rounded-xl border border-black/[0.08] bg-background transition-colors',
        'dark:border-white/[0.1]'
      )}
    >
      {icon}
      <span className="text-[13px] font-medium leading-none">{label}</span>
    </button>
  )
}

function ChatStep({
  client,
  sourceChatId,
  activeProjectId,
  projects,
  allTabGroups,
  cachedSessions,
  onBack,
  onPickChat,
  onPickNewChat
}: {
  client: LocalAgentClient
  sourceChatId: string
  activeProjectId: string | null
  projects: AgentProject[]
  allTabGroups: SessionGroup[]
  cachedSessions: AgentSession[]
  onBack: () => void
  onPickChat: (chatId: string) => void
  onPickNewChat: () => void
}) {
  return (
    <div className="animate-in fade-in slide-in-from-right-1 flex h-full min-h-0 min-w-0 flex-col overflow-hidden duration-[180ms]">
      <div className="flex shrink-0 items-center gap-2 border-b border-border/50 px-3 py-2">
        <button
          type="button"
          onClick={onBack}
          className="text-muted-foreground hover:text-foreground hover:bg-muted inline-flex h-7 items-center gap-1 rounded-md px-2 text-[12px]"
        >
          <ArrowLeft className="size-3.5" />
          <span>Back</span>
        </button>
      </div>
      <div className="flex min-h-0 min-w-0 flex-1 flex-col items-center justify-center gap-3 overflow-hidden p-4">
        <h2 className="text-foreground shrink-0 text-center text-[14px] font-medium">
          Pick a chat for the split
        </h2>
        <SplitChatPickerPanel
          client={client}
          sourceChatId={sourceChatId}
          activeProjectId={activeProjectId}
          projects={projects}
          allTabGroups={allTabGroups}
          cachedSessions={cachedSessions}
          onPick={onPickChat}
        />
      </div>
      <div className="border-border/50 shrink-0 border-t px-3 py-2">
        <button
          type="button"
          onClick={onPickNewChat}
          className="hover:bg-muted text-muted-foreground hover:text-foreground inline-flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-[12px]"
        >
          <Plus className="size-3.5" />
          <span>Start new chat</span>
        </button>
      </div>
    </div>
  )
}
