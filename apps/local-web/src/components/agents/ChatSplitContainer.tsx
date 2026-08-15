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
   * Returns the per-panel header props (files/terminal/preview/CLI/
   * ellipsis + state + callbacks) for the given chatId. Applied to the
   * header slot of each `SplitFragment`.
   */
  buildHeaderProps: (
    chatId: string,
    focused: boolean,
    onFocusPanel: () => void
  ) => ChatSplitPanelHeaderProps
  projects: AgentProject[]
  /**
   * Picker context and callbacks — used in two situations:
   *  1. Pending mode (created from "Create split view", second chat
   *     still to be picked). `onPickPartner` promotes the group.
   *  2. Add mode (user clicked "+" on the right edge to add one more
   *     chat to the assembled split). `onAddChat` appends to the group.
   * Both pickers look identical; only the callback differs on pick.
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

  // While the user is assembling a split, the picker card behaves like
  // any other panel: hover ring on mouse-over, border-primary/60 when
  // clicked ("focused"). Clicking chat A takes focus away from the
  // picker. Only one card can be focused at a time, same as a real split.
  const [pickerFocused, setPickerFocused] = useState(false)
  // Add mode: the user clicked "+" on the right edge to append ONE more
  // chat to an already-formed split. An extra picker panel opens on the
  // right; picking → addToGroup; cancelling (X) → just closes the
  // picker, the group stays intact.
  const [addingPanel, setAddingPanel] = useState(false)
  // Hitbox at the far-right edge of the panel: on mouseEnter within the
  // last ~12px, the "+" column expands with an animation (pushing chats
  // to the left). On mouseLeave it collapses. No visible element by
  // default — just hitbox + animated result.
  const [gutterHovered, setGutterHovered] = useState(false)

  if (chatIds.length === 0) return null

  // Picker slot shows when:
  //  - group is pending (still assembling the 2nd chat).
  //  - real group + the user clicked "+" to add one more chat.
  const hasPickerSlot = isPending || addingPanel
  const totalPanels = hasPickerSlot ? chatIds.length + 1 : chatIds.length
  // The "+" gutter only shows for real (non-pending) splits and when
  // we're not already adding a panel.
  const canShowAddSlot =
    !isPending && !addingPanel && Boolean(pickerContext)

  return (
    <div
      className="relative flex h-full min-h-0 min-w-0 flex-1"
      // Fallback: when the mouse leaves the whole container (via the
      // window's right edge or any other app edge), the column's own
      // mouseleave doesn't fire because the mouse exits the document
      // directly. Listening at the outer container guarantees collapse.
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
        // A chat is focused when it's the activeChatId AND the picker
        // isn't focused (only one card holds visual focus).
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
            OUTER picker card: same visual states as a SplitFragment —
            focused (border-primary/60) when the user is interacting,
            hover ring otherwise. The X in the header cancels: if
            pending, dissolves the whole group; if add mode, just
            closes this panel without touching the group.
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
            {/* X at the top-right of the outer card (Chrome dual-view
                pattern). If pending → dissolves the group. If add mode
                → closes this picker panel without touching the group. */}
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
              Centered layout: title "Pick a chat…" up top (outside the
              widget box) and the picker below. Both horizontally
              centered in the outer card. A vertical gap keeps them
              aligned like a message + form.
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
                  // Reset local state BEFORE firing the group change:
                  // otherwise, when the picker disappears and the new
                  // elements (chat B + "+" hitbox) appear, React fires
                  // automatic mouseenter/focus on whatever ends up
                  // under the cursor — which would activate the "+"
                  // gutter just from the layout shift, not from real
                  // user intent.
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
      Animated "+" column: invisible by default (w-0). Expands to 48px
      when the mouse enters the far-right hitbox. Collapses when the
      mouse leaves the column. The column lives in the flex row (not
      absolute) so expanding pushes the chats to the left with a smooth
      transition.
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
      Invisible hitbox pinned to the far-right edge — captures hover on
      the last ~12px and toggles the animated gutter. Zero layout
      footprint (absolute) and no visual appearance.
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
             * Each split panel is an independent card (Chrome dual-view
             * pattern). Border + rounded + bg-background wrap it as a
             * discrete box; focused bumps the border to `primary/60`
             * so it's crystal-clear which chat the user is on while
             * the others stay readable but secondary.
             */
            /*
             * `duration-300 ease-out` for the focused/non-focused
             * transition: the border grows softly instead of snapping
             * when the user clicks another panel. Hover ring keeps its
             * short timing (Tailwind's 150ms default) so it reacts
             * instantly to the mouse.
             */
            /*
             * Split panel visual: only `border-color` distinguishes
             * focused vs non-focused (plus the hover ring when not
             * focused). We used to add `shadow-md` too, but it was
             * imperceptible and expensive per paint frame.
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
            The panel's composer renders as an embedded bar (docked to
            the bottom with a slide animation) — visibility + animation
            are handled by `SessionChatBody` based on `splitMode`. We
            just pass the flag here; the composer stays mounted always
            so per-panel draft text is preserved.
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
