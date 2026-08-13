import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  SessionGroup
} from '@sandwalk/agent-ui-core'
import { X } from 'lucide-react'
import { useState } from 'react'

import {
  ChatSplitPanelHeader,
  type ChatSplitPanelHeaderProps
} from '@/components/agents/ChatSplitPanelHeader'
import {
  SessionChatMount,
  type SessionChatMountProps
} from '@/components/agents/SessionChatMount'
import { SplitChatPickerPanel } from '@/components/agents/SplitChatPickerPanel'
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
  /**
   * Contexto y callbacks del picker — sólo se usa cuando el grupo está en
   * modo pending (creado desde "Create split view", falta elegir el
   * segundo chat). Cuando falta, un panel del split se pinta como el
   * `SplitChatPickerPanel` en vez de un chat.
   */
  pickerContext?: {
    client: LocalAgentClient
    activeProjectId: string | null
    allTabGroups: SessionGroup[]
    onPickPartner: (chatId: string) => void
    onCancelPending: () => void
  }
}

export function ChatSplitContainer({
  group,
  sessions,
  buildMountProps,
  onFocusChat,
  buildHeaderProps,
  projects,
  pickerContext
}: ChatSplitContainerProps) {
  const chatIds = group.chatIds
  const activeChatId = group.activeChatId
  const isPending = Boolean(group.isPending)

  // Cuando el usuario está armando un split, la card del picker se
  // comporta como un panel más: hover ring cuando pasa el mouse,
  // border-primary/60 cuando la clickea (pasa a "focused"). Al hacer
  // click en el chat A el picker pierde el foco. Sólo puede haber una
  // card focused a la vez, como en un split real.
  const [pickerFocused, setPickerFocused] = useState(false)

  if (chatIds.length === 0) return null

  // En modo pending, agregamos un slot "picker" al final del split.
  // Ese slot NO es un chat — es el SplitChatPickerPanel para elegir el
  // segundo compañero. Al elegir, `promotePendingGroup` en el store
  // agrega el chat al grupo y limpia el flag, y este mismo layout
  // renderiza los dos paneles de chat sin salto visual.
  const totalPanels = isPending ? chatIds.length + 1 : chatIds.length

  return (
    <ResizablePanelGroup
      direction="horizontal"
      className="min-h-0 min-w-0 flex-1 gap-2 p-2"
      autoSaveId={
        isPending ? undefined : `fastfold.split-group-${group.id}`
      }
    >
      {chatIds.map((chatId, index) => {
        // El chat es focused si es el activeChatId Y el picker no está
        // focused (solo puede haber uno con foco visual).
        const isFocused = chatId === activeChatId && !pickerFocused
        const isLast = index === totalPanels - 1
        const props = buildMountProps(chatId)
        const chatSession = sessions.find(s => s.id === chatId) || null
        const focusPanel = () => {
          if (pickerFocused) setPickerFocused(false)
          if (chatId !== activeChatId) onFocusChat(chatId)
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
      {isPending && pickerContext ? (
        <ResizablePanel
          id={`split-picker-${group.id}`}
          order={999}
          defaultSize={100}
          minSize={20}
          className="min-w-0"
        >
          {/*
            Card EXTERIOR del picker: mismos estados visuales que un
            SplitFragment — focused (border-primary/60) cuando el usuario
            está interactuando con el picker, hover ring en otro caso.
            Sólo puede haber una card focused a la vez: al clickear el
            picker, el chat A pierde el focus y viceversa. La X arriba
            a la derecha cancela el pending group entero.
          */}
          <div
            className={cn(
              'bg-background relative flex h-full min-w-0 flex-col overflow-hidden rounded-lg border transition-[border-color] duration-300 ease-out',
              pickerFocused
                ? 'border-primary/60'
                : 'border-border/50 hover:ring-2 hover:ring-inset hover:ring-muted-foreground/25'
            )}
            onMouseDownCapture={() => {
              if (!pickerFocused) setPickerFocused(true)
            }}
            onFocusCapture={() => {
              if (!pickerFocused) setPickerFocused(true)
            }}
          >
            <button
              type="button"
              onClick={pickerContext.onCancelPending}
              aria-label="Cancel split"
              className="text-muted-foreground hover:text-foreground hover:bg-muted absolute right-2 top-2 z-10 inline-flex size-7 items-center justify-center rounded-md"
            >
              <X className="size-4" />
            </button>
            {/*
              Layout centrado: título "Elegí un chat…" arriba libre
              (fuera de la caja del widget) y el picker debajo. Ambos
              centrados horizontalmente en la card exterior. Un gap
              vertical los mantiene alineados como un mensaje +
              formulario.
            */}
            <div className="flex h-full min-h-0 min-w-0 flex-col items-center justify-center gap-3 overflow-hidden p-4">
              <h2 className="text-foreground shrink-0 text-center text-[14px] font-medium">
                Pick a chat for the split
              </h2>
              <SplitChatPickerPanel
                client={pickerContext.client}
                sourceChatId={chatIds[0]}
                activeProjectId={pickerContext.activeProjectId}
                projects={projects}
                allTabGroups={pickerContext.allTabGroups}
                onPick={pickerContext.onPickPartner}
              />
            </div>
          </div>
        </ResizablePanel>
      ) : null}
    </ResizablePanelGroup>
  )
}

export function SplitFragment({
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
