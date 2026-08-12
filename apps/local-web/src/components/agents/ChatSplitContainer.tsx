import type {
  AgentProject,
  AgentSession,
  SessionGroup
} from '@sandwalk/agent-ui-core'

import {
  ChatSplitPanelHeader,
  type ChatSplitPanelHeaderProps
} from '@/components/agents/ChatSplitPanelHeader'
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
  /**
   * Recibe los props del header por panel (files/terminal/preview/CLI/
   * ellipsis + estado + callbacks) para el chatId dado. Se aplica al slot
   * del header de cada `SplitFragment`.
   */
  buildHeaderProps: (
    chatId: string,
    focused: boolean,
    onFocusPanel: () => void
  ) => ChatSplitPanelHeaderProps
  projects: AgentProject[]
}

export function ChatSplitContainer({
  group,
  sessions,
  buildMountProps,
  onFocusChat,
  buildHeaderProps
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
        const focusPanel = () => {
          if (!isFocused) onFocusChat(chatId)
        }
        const headerProps = buildHeaderProps(chatId, isFocused, focusPanel)
        return (
          <SplitFragment
            key={chatId}
            chatId={chatId}
            isFocused={isFocused}
            isLast={isLast}
            chatSession={chatSession}
            props={props}
            headerProps={headerProps}
            onFocus={focusPanel}
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
  headerProps,
  onFocus
}: {
  chatId: string
  isFocused: boolean
  isLast: boolean
  chatSession: AgentSession | null
  props: Omit<SessionChatMountProps, 'perSessionArgs'> & {
    perSessionArgs: SessionChatMountProps['perSessionArgs']
  }
  headerProps: ChatSplitPanelHeaderProps
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
            /*
             * Panel del split: solo el `border-color` distingue focused vs
             * no-focused (más el ring en hover cuando no está focused).
             * Antes había `shadow-md` acompañando pero era imperceptible
             * y encarecía el paint frame a frame.
             */
            'bg-background relative flex h-full min-w-0 flex-col overflow-hidden rounded-lg border transition-[border-color] duration-300 ease-out',
            isFocused
              ? 'border-primary/60'
              : 'border-border/50 hover:ring-2 hover:ring-inset hover:ring-muted-foreground/25'
          )}
          onMouseDownCapture={onFocus}
          onFocusCapture={onFocus}
        >
          <ChatSplitPanelHeader {...headerProps} />
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
