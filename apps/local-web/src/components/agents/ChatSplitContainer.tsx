import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  SessionGroup
} from '@sandwalk/agent-ui-core'
import { Plus, X } from 'lucide-react'
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
   * Contexto y callbacks del picker — se usa en dos situaciones:
   *  1. Modo pending (creado desde "Create split view", falta elegir el
   *     segundo chat). `onPickPartner` promueve el grupo.
   *  2. Modo add (usuario clickeó el "+" a la derecha para agregar un
   *     chat más al split ya armado). `onAddChat` agrega al grupo.
   * Ambos pickers son visualmente idénticos; sólo cambia qué callback
   * se dispara al elegir.
   */
  pickerContext?: {
    client: LocalAgentClient
    activeProjectId: string | null
    allTabGroups: SessionGroup[]
    onPickPartner: (chatId: string) => void
    onCancelPending: () => void
    onAddChat: (chatId: string) => void
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
  // Add mode: usuario clickeó el "+" a la derecha para agregar un chat
  // MÁS al split ya armado. Se abre un panel picker adicional a la
  // derecha; elegir → addToGroup; cancelar (X) → sólo cierra el picker,
  // el grupo queda intacto.
  const [addingPanel, setAddingPanel] = useState(false)
  // Zona sensible en el borde derecho extremo: al mouseEnter en los
  // últimos ~12px del panel, se expande la columna del "+" con
  // animación (empuja los chats a la izquierda). Al mouseLeave se
  // colapsa. No es un elemento visible por default, sólo hitbox +
  // resultado animado.
  const [gutterHovered, setGutterHovered] = useState(false)

  if (chatIds.length === 0) return null

  // Slot picker aparece cuando:
  //  - grupo pending (se está armando el 2do).
  //  - grupo real y usuario clickeó "+" para agregar un chat más.
  const hasPickerSlot = isPending || addingPanel
  const totalPanels = hasPickerSlot ? chatIds.length + 1 : chatIds.length
  // El "+" a la derecha solo aparece en splits reales (no pending) y
  // cuando no estamos ya agregando un panel.
  const canShowAddSlot =
    !isPending && !addingPanel && Boolean(pickerContext)

  return (
    <div
      className="relative flex h-full min-h-0 min-w-0 flex-1"
      // Fallback: cuando el mouse sale del contenedor entero (por el
      // borde derecho de la ventana o cualquier otro edge del app), el
      // mouseleave de la columna no se dispara porque el mouse va
      // directo fuera del document. Escuchamos a nivel contenedor
      // externo para asegurar el colapso.
      onMouseLeave={() => {
        if (gutterHovered) setGutterHovered(false)
      }}
    >
    <ResizablePanelGroup
      direction="horizontal"
      className="min-h-0 min-w-0 flex-1 gap-2 p-2"
      autoSaveId={
        hasPickerSlot ? undefined : `fastfold.split-group-${group.id}`
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
      {hasPickerSlot && pickerContext ? (
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
            está interactuando, hover ring en otro caso. La X en el
            header cancela: si es pending, disuelve el grupo entero; si
            es add mode, sólo cierra este panel sin tocar el grupo.
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
            {/* X arriba a la derecha de la card exterior (patrón
                Chrome dual-view). Si es pending → disuelve el grupo.
                Si es add mode → cierra este panel picker sin tocar el
                grupo. */}
            <button
              type="button"
              onClick={() => {
                if (isPending) {
                  pickerContext.onCancelPending()
                } else {
                  setAddingPanel(false)
                  setPickerFocused(false)
                }
              }}
              aria-label="Cancel"
              className="text-muted-foreground hover:text-foreground hover:bg-muted absolute right-2 top-2 z-10 inline-flex size-7 items-center justify-center rounded-md"
            >
              <X className="size-4" />
            </button>
            {/*
              Layout centrado: título "Pick a chat…" arriba libre (fuera
              de la caja del widget) y el picker debajo. Ambos centrados
              horizontalmente en la card exterior. Un gap vertical los
              mantiene alineados como un mensaje + formulario.
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
                cachedSessions={sessions}
                onPick={chatId => {
                  // Resetear estados locales antes de disparar el
                  // cambio de grupo: si no lo hacemos, cuando el picker
                  // desaparece y aparecen los nuevos elementos (chat B
                  // + hitbox del "+"), React dispara mouseenter/focus
                  // automático en los elementos que quedan bajo el
                  // mouse — lo cual activaría el gutter del "+" solo
                  // por el cambio de layout, no por intención real del
                  // usuario.
                  setGutterHovered(false)
                  setPickerFocused(false)
                  if (isPending) {
                    pickerContext.onPickPartner(chatId)
                  } else {
                    pickerContext.onAddChat(chatId)
                    setAddingPanel(false)
                  }
                }}
              />
            </div>
          </div>
        </ResizablePanel>
      ) : null}
    </ResizablePanelGroup>
    {/*
      Columna animada del "+": invisible por defecto (w-0). Se expande
      a 48px cuando el mouse entra en la hitbox derecha extrema. Al
      salir el mouse de la columna se colapsa. La columna vive en el
      flex row (no absolute) así que al expandirse empuja los chats a
      la izquierda con transition suave.
    */}
    {canShowAddSlot ? (
      <div
        className={cn(
          'bg-muted/60 flex h-full shrink-0 items-center justify-center overflow-hidden transition-[width] duration-200 ease-out',
          gutterHovered ? 'w-12' : 'w-0'
        )}
        onMouseLeave={() => setGutterHovered(false)}
      >
        <button
          type="button"
          onClick={() => setAddingPanel(true)}
          aria-label="Add another chat to the split"
          className={cn(
            'bg-background text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-8 items-center justify-center rounded-full border shadow-sm transition-opacity duration-150',
            gutterHovered ? 'opacity-100' : 'opacity-0'
          )}
        >
          <Plus className="size-4" />
        </button>
      </div>
    ) : null}
    {/*
      Hitbox invisible pegada al borde derecho extremo — captura el
      hover en los últimos ~12px y activa el gutter animado. No ocupa
      espacio en el layout (es absolute), y no se muestra visualmente.
    */}
    {canShowAddSlot ? (
      <div
        className="absolute right-0 top-0 h-full w-3"
        onMouseEnter={() => setGutterHovered(true)}
      />
    ) : null}
    </div>
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
