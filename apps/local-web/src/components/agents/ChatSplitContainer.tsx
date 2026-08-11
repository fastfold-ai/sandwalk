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
      className="min-h-0 min-w-0 flex-1 gap-2 p-2"
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
            /*
             * Cada panel del split es una tarjeta independiente (patrón
             * Chrome dual-view). Border + rounded + bg-background lo envuelven
             * como un cuadro propio; el focused sube el borde a `primary/60`
             * + shadow para dejar clarísimo en cuál chat está el usuario
             * mientras los otros quedan legibles pero secundarios.
             */
            /*
             * `duration-300 ease-out` para el paso focused/no-focused: el
             * border/shadow crecen suave en vez de aparecer de golpe cuando el
             * usuario clickea otro panel. El ring del hover se mantiene con
             * su timing corto (150 ms default de Tailwind) para que reaccione
             * inmediato al mouse.
             */
            'bg-background relative flex h-full min-w-0 flex-col overflow-hidden rounded-lg border transition-[border-color,box-shadow] duration-300 ease-out',
            isFocused
              ? 'border-primary/60 shadow-md'
              : 'border-border/50 shadow-none hover:ring-2 hover:ring-inset hover:ring-muted-foreground/25'
          )}
          onMouseDownCapture={onFocus}
          onFocusCapture={onFocus}
        >
          {/*
            El composer del panel se pinta como barra embedded (pegada al
            bottom con animación slide) — la visibilidad y la animación las
            maneja `SessionChatBody` a partir de `splitMode`. Acá solo se le
            pasa el flag; el composer sigue mounted siempre para preservar
            el texto que estaba escribiendo el usuario en cada panel.
          */}
          <div
            className="flex h-full min-w-0 flex-1 flex-col"
            aria-label={`Chat panel for ${chatSession?.title || 'session'}`}
          >
            <SessionChatMount {...props} splitMode={{ focused: isFocused }} />
          </div>
        </div>
      </ResizablePanel>
      {!isLast ? (
        <ResizableHandle
          className="w-0 bg-transparent after:bg-transparent"
        />
      ) : null}
    </>
  )
}
