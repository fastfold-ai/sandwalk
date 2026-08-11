import type { AgentSession, SessionGroup } from '@sandwalk/agent-ui-core'

import {
  SessionChatMount,
  type SessionChatMountProps
} from '@/components/agents/SessionChatMount'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { cn } from '@/lib/utils'

/**
 * Renders a horizontal split of N chats — one panel per chatId in the group.
 * Each panel is a fully-live `SessionChatMount` (mensajes SSE, composer,
 * sandbox, actions) instantiated independently, so composer state and IME
 * composition survive focus changes.
 *
 * Focus behavior (from research: VSCode / Zed / Arc pattern):
 *   - Focused panel gets a soft accent inset ring + accent border on its
 *     header strip; other panels stay legible (no dimming).
 *   - Composer visibility is per-panel: only the focused panel shows its
 *     composer (opacity: 1 + pointer-events: auto); the others keep their
 *     composer mounted at opacity: 0 + pointer-events: none so typing state
 *     and IME sessions are preserved without remounts.
 *   - Clicking anywhere in a panel body promotes it to focused via
 *     `onFocusChat(chatId)`.
 */

export type ChatSplitContainerProps = {
  group: SessionGroup
  sessions: AgentSession[]
  buildMountProps: (chatId: string) => Omit<SessionChatMountProps, 'perSessionArgs'> & {
    perSessionArgs: SessionChatMountProps['perSessionArgs']
  }
  onFocusChat: (chatId: string) => void
}

export function ChatSplitContainer({
  group,
  sessions,
  buildMountProps,
  onFocusChat
}: ChatSplitContainerProps) {
  const chatIds = group.chatIds
  const activeChatId = group.activeChatId

  if (chatIds.length === 0) return null

  return (
    <ResizablePanelGroup
      direction="horizontal"
      className="min-h-0 min-w-0 flex-1"
      autoSaveId={`fastfold.split-group-${group.id}`}
    >
      {chatIds.map((chatId, index) => {
        const isFocused = chatId === activeChatId
        const isLast = index === chatIds.length - 1
        const props = buildMountProps(chatId)
        const chatSession = sessions.find(s => s.id === chatId) || null
        return (
          <SplitFragment
            key={chatId}
            chatId={chatId}
            isFocused={isFocused}
            isLast={isLast}
            chatSession={chatSession}
            props={props}
            onFocus={() => {
              if (!isFocused) onFocusChat(chatId)
            }}
          />
        )
      })}
    </ResizablePanelGroup>
  )
}

function SplitFragment({
  chatId,
  isFocused,
  isLast,
  chatSession,
  props,
  onFocus
}: {
  chatId: string
  isFocused: boolean
  isLast: boolean
  chatSession: AgentSession | null
  props: Omit<SessionChatMountProps, 'perSessionArgs'> & {
    perSessionArgs: SessionChatMountProps['perSessionArgs']
  }
  onFocus: () => void
}) {
  return (
    <>
      <ResizablePanel
        id={`split-${chatId}`}
        order={100}
        defaultSize={100}
        minSize={20}
        className="min-w-0"
      >
        <div
          className={cn(
            'relative flex h-full min-w-0 flex-col transition-shadow',
            /*
             * Focused panel indicator (research-recommended: subtle inset ring +
             * accent hairline, do NOT dim inactive panels).
             */
            isFocused
              ? 'ring-primary/40 shadow-[inset_0_0_0_1px_hsl(var(--primary)/0.4)] ring-1 ring-inset'
              : ''
          )}
          onMouseDownCapture={onFocus}
          onFocusCapture={onFocus}
        >
          {/*
            Composer visibility: focused panel shows a real composer; others
            keep it mounted but invisible so typing / IME / file chips survive.
          */}
          <div
            className={cn(
              'flex h-full min-w-0 flex-1 flex-col',
              !isFocused &&
                '[&_[data-composer-slot]]:pointer-events-none [&_[data-composer-slot]]:opacity-0'
            )}
            aria-label={`Chat panel for ${chatSession?.title || 'session'}`}
          >
            <SessionChatMount {...props} />
          </div>
        </div>
      </ResizablePanel>
      {!isLast ? (
        <ResizableHandle
          className="w-px bg-transparent after:bg-transparent"
        />
      ) : null}
    </>
  )
}
