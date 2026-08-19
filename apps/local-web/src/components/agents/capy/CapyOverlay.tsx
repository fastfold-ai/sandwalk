import { Archive, Minus, Pin, Upload, X } from 'lucide-react'
import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSkill,
  AgentSession,
  BackendHealth,
  McpServer,
  RuntimeSettings
} from '@sandwalk/agent-ui-core'
import { isSessionGroupId } from '@sandwalk/agent-ui-core'

import capyLogo from '@/assets/capy-logo.png'
import { CapyChat } from '@/components/agents/capy/CapyChat'
import { CapyComposer } from '@/components/agents/capy/CapyComposer'
import '@/components/agents/capy/CapyOverlay.css'
import { useCapyHandsFree } from '@/hooks/useCapyHandsFree'
import { useCapySession } from '@/hooks/useCapySession'
import { useCapyWindow } from '@/hooks/useCapyWindow'
import { CAPY_MIN_HEIGHT, CAPY_MIN_WIDTH, formatCapyUnreadBadge } from '@/lib/capy-ui'
import { isDraftAgentSessionId, isReservedAgentRouteId } from '@/lib/draft-agent'
import type { ComposerModelOption } from '@/lib/composer-models'
import { cn } from '@/lib/utils'

function clampSize(width: number, height: number) {
  return {
    width: Math.max(CAPY_MIN_WIDTH, Math.min(width, window.innerWidth - 16)),
    height: Math.max(CAPY_MIN_HEIGHT, Math.min(height, window.innerHeight - 16))
  }
}

const SUGGESTIONS = [
  'Capy, what can you help me with?',
  'Start 3 sessions and say hi',
  'Run doctor and summarize diagnostics',
  'List bench suites and start a run',
  'Show last bench results and token usage'
]

export function CapyOverlay({
  client,
  health,
  chats,
  skills,
  mcpServers,
  modelOptions,
  runtimeSettings,
  setRuntimeSettings,
  loadModelOptions,
  onSessionId,
  activeProjectId = null,
  activeChatId = null
}: {
  client: LocalAgentClient
  health: BackendHealth | null
  chats: AgentSession[]
  skills: AgentSkill[]
  mcpServers: McpServer[]
  modelOptions: ComposerModelOption[]
  runtimeSettings: RuntimeSettings | null
  setRuntimeSettings: Dispatch<SetStateAction<RuntimeSettings | null>>
  loadModelOptions: () => Promise<void>
  onSessionId?: (id: string | null) => void
  activeProjectId?: string | null
  activeChatId?: string | null
}) {
  const { state, persist } = useCapyWindow()
  const enabled = Boolean(health)
  const capy = useCapySession({ client, health, enabled })
  const [unreadCount, setUnreadCount] = useState(0)
  const [dropActive, setDropActive] = useState(false)
  const wasRunning = useRef(false)
  const handsFree = useCapyHandsFree({
    enabled: Boolean(health),
    send: text => capy.send(text),
    runActive: capy.chat.runActive
  })
  const drag = useRef<{ dx: number; dy: number } | null>(null)
  const dragged = useRef(false)
  const resize = useRef<{
    edge: 'e' | 'w' | 's' | 'se' | 'sw'
    startX: number
    startY: number
    startW: number
    startH: number
    startLeft: number
  } | null>(null)
  const stateRef = useRef(state)
  stateRef.current = state
  const rootRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    onSessionId?.(capy.session?.id ?? null)
  }, [capy.session?.id, onSessionId])

  useEffect(() => {
    if (!health) return
    const sessionId =
      !activeChatId ||
      activeChatId === capy.session?.id ||
      isDraftAgentSessionId(activeChatId) ||
      isReservedAgentRouteId(activeChatId) ||
      isSessionGroupId(activeChatId)
        ? null
        : activeChatId
    void client.setCapyScope({
      projectId: activeProjectId,
      sessionId
    })
  }, [client, health, activeProjectId, activeChatId, capy.session?.id])

  useEffect(() => {
    if (state.minimized && wasRunning.current && !capy.chat.runActive) {
      setUnreadCount(count => count + 1)
    }
    wasRunning.current = capy.chat.runActive
  }, [capy.chat.runActive, state.minimized])

  useEffect(() => {
    if (state.open && !state.minimized) setUnreadCount(0)
  }, [state.minimized, state.open])

  useEffect(() => {
    if (!state.open || state.minimized || state.locked) return
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      if (rootRef.current?.contains(target)) return
      if (
        target.closest(
          '[data-capy-trigger], [data-radix-popper-content-wrapper], [data-radix-menu-content], [role="listbox"], [role="dialog"]'
        )
      ) {
        return
      }
      const current = stateRef.current
      persist({ ...current, open: false, minimized: false })
    }
    document.addEventListener('pointerdown', onPointerDown, true)
    return () => document.removeEventListener('pointerdown', onPointerDown, true)
  }, [persist, state.locked, state.minimized, state.open])

  const dragKind = useRef<'window' | 'minimized' | null>(null)

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      const current = stateRef.current
      if (resize.current) {
        const job = resize.current
        const fromWest = job.edge === 'w' || job.edge === 'sw'
        const fromEast = job.edge === 'e' || job.edge === 'se'
        const fromSouth = job.edge === 's' || job.edge === 'se' || job.edge === 'sw'
        const nextWidth = fromWest
          ? job.startW - (event.clientX - job.startX)
          : fromEast
            ? job.startW + (event.clientX - job.startX)
            : current.width
        const nextHeight = fromSouth
          ? job.startH + (event.clientY - job.startY)
          : current.height
        const size = clampSize(nextWidth, nextHeight)
        const right = job.startLeft + job.startW
        const x = fromWest ? Math.max(8, right - size.width) : current.x
        persist({ ...current, ...size, x })
        return
      }
      if (!drag.current) return
      const x = Math.max(
        8,
        Math.min(window.innerWidth - 80, event.clientX - drag.current.dx)
      )
      const y = Math.max(
        8,
        Math.min(window.innerHeight - 80, event.clientY - drag.current.dy)
      )
      if (Math.abs(x - current.x) > 3 || Math.abs(y - current.y) > 3) {
        dragged.current = true
      }
      persist({ ...current, x, y })
    }
    const onUp = () => {
      const kind = dragKind.current
      const wasDrag = dragged.current
      drag.current = null
      resize.current = null
      dragKind.current = null
      if (kind === 'minimized' && !wasDrag) {
        setUnreadCount(0)
        persist({ ...stateRef.current, open: true, minimized: false })
      }
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [persist])

  if (!health) return null
  if (!state.open && !state.minimized) return null

  const startDrag =
    (kind: 'window' | 'minimized') => (event: ReactPointerEvent<HTMLElement>) => {
      if (kind === 'window' && (event.target as HTMLElement | null)?.closest('button')) {
        return
      }
      event.preventDefault()
      event.stopPropagation()
      dragged.current = false
      dragKind.current = kind
      const current = stateRef.current
      drag.current = {
        dx: event.clientX - current.x,
        dy: event.clientY - current.y
      }
      event.currentTarget.setPointerCapture?.(event.pointerId)
    }
  const onResizeDown =
    (edge: 'e' | 'w' | 's' | 'se' | 'sw') =>
    (event: ReactPointerEvent<HTMLElement>) => {
      event.stopPropagation()
      event.preventDefault()
      const current = stateRef.current
      resize.current = {
        edge,
        startX: event.clientX,
        startY: event.clientY,
        startW: current.width,
        startH: current.height,
        startLeft: current.x
      }
    }
  const stopDrag = (event: ReactPointerEvent<HTMLElement>) => {
    event.stopPropagation()
  }

  if (state.minimized) {
    const working = capy.chat.runActive || handsFree.transcribing
    const unreadLabel = formatCapyUnreadBadge(unreadCount)
    return (
      <div
        data-capy-root
        data-no-window-drag
        className="fixed z-[80]"
        style={{ left: state.x, top: state.y }}
      >
        <div
          className={cn(
            'relative size-14 cursor-grab rounded-full shadow-[0_12px_40px_-8px_rgba(0,0,0,0.55)] active:cursor-grabbing dark:shadow-[0_16px_48px_-6px_rgba(0,0,0,0.8)]',
            working && 'text-sky-400',
            handsFree.recording && 'ring-2 ring-red-500 ring-offset-2 ring-offset-background',
            handsFree.transcribing &&
              !capy.chat.runActive &&
              'ring-2 ring-amber-400 ring-offset-2 ring-offset-background'
          )}
          onPointerDown={startDrag('minimized')}
          role="button"
          tabIndex={0}
          aria-busy={working}
          aria-label={
            working
              ? 'Capy is working.'
              : unreadLabel
                ? `Open Capy. ${unreadCount} new ${unreadCount === 1 ? 'reply' : 'replies'}.`
                : 'Open Capy. Double-tap Control for hands-free voice.'
          }
          title={
            working
              ? 'Capy is working'
              : 'Double-tap Control to talk to Capy'
          }
        >
          <img
            src={capyLogo}
            alt=""
            className={cn(
              'size-14 rounded-full object-cover',
              working && 'capy-working-hue'
            )}
          />
          {unreadLabel ? (
            <span className="capy-unread-badge" aria-hidden>
              {unreadLabel}
            </span>
          ) : null}
        </div>
        <button
          type="button"
          className="bg-background border-border absolute -left-1 -top-1 z-10 size-5 rounded-full border text-[10px]"
          onPointerDown={stopDrag}
          onClick={() => persist({ ...state, open: false, minimized: false })}
          aria-label="Close Capy"
        >
          <X className="mx-auto size-3" />
        </button>
      </div>
    )
  }

  const empty = capy.chat.messages.length === 0 && !capy.chat.liveDelta
  return (
    <div
      ref={rootRef}
      data-capy-root
      data-no-window-drag
      className={cn(
        'border-border bg-background fixed z-[80] flex flex-col overflow-hidden rounded-2xl border shadow-[0_24px_80px_-12px_rgba(0,0,0,0.65),0_8px_24px_-8px_rgba(0,0,0,0.45)] dark:shadow-[0_28px_90px_-10px_rgba(0,0,0,0.85),0_10px_32px_-6px_rgba(0,0,0,0.7)]',
        dropActive && 'border-sky-500/60 ring-2 ring-sky-500/25'
      )}
      style={{
        left: state.x,
        top: state.y,
        width: Math.min(state.width, window.innerWidth - 16),
        height: Math.min(state.height, window.innerHeight - 16)
      }}
    >
      <div
        className="relative flex cursor-grab items-center px-2 py-2 active:cursor-grabbing"
        onPointerDown={startDrag('window')}
      >
        <div className="z-10 flex shrink-0 items-center" onPointerDown={stopDrag}>
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground p-1"
            aria-label="Close Capy"
            onClick={() => persist({ ...state, open: false, minimized: false })}
          >
            <X className="size-4" />
          </button>
          <button
            type="button"
            className={cn(
              'text-muted-foreground hover:text-foreground rounded-md p-1',
              state.locked && 'bg-muted text-foreground'
            )}
            title={
              state.locked
                ? 'Unpin: click outside to close'
                : 'Pin: Keep Capy window open'
            }
            aria-label={
              state.locked
                ? 'Unpin Capy'
                : 'Pin: Keep Capy window open'
            }
            aria-pressed={state.locked}
            onClick={() => persist({ ...state, locked: !state.locked })}
          >
            <Pin className="size-4" />
          </button>
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground p-1"
            aria-label="Minimize Capy"
            onClick={() => persist({ ...state, open: false, minimized: true })}
          >
            <Minus className="size-4" />
          </button>
        </div>
        <div className="pointer-events-none absolute inset-0 z-0 flex items-center justify-center gap-1.5">
          <img src={capyLogo} alt="" className="size-5 rounded-full object-cover" />
          <div className="text-sm font-medium">Capy</div>
        </div>
        <div
          className="z-10 ml-auto flex shrink-0 items-center"
          onPointerDown={stopDrag}
        >
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground p-1"
            title="Archive and start new chat"
            aria-label="Archive and start new chat"
            onClick={() => void capy.reset()}
          >
            <Archive className="size-4" />
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        {empty ? (
          <div className="flex h-full flex-col items-center justify-center px-6 py-4 text-center">
            <img src={capyLogo} alt="" className="size-28 object-contain" />
            <div className="text-foreground/90 mt-4 max-w-[440px] space-y-1 text-[13px] leading-5">
              <p>This is Capy.</p>
              <p>Your meta agent for everything you want to do in Sandwalk.</p>
              <p>Try asking Capy:</p>
            </div>
            <div className="mt-3 flex max-w-[460px] flex-wrap justify-center gap-1.5">
              {SUGGESTIONS.map(text => (
                <button
                  key={text}
                  type="button"
                  className="border-border bg-muted/40 hover:bg-muted rounded-full border px-2.5 py-1 text-xs"
                  onClick={() => capy.setChat(prev => ({ ...prev, composer: text }))}
                >
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <CapyChat
            client={client}
            session={capy.session}
            chat={capy.chat}
            chats={chats}
            onChatChange={capy.setChat}
            onStop={() => void capy.stop()}
          />
        )}
      </div>
      {dropActive ? (
        <div
          className="pointer-events-none absolute inset-0 z-40 flex flex-col items-center justify-center gap-2 bg-sky-500/10 backdrop-blur-[1px]"
          aria-hidden
        >
          <Upload className="size-7 text-sky-700 dark:text-sky-300" />
          <p className="text-sm font-medium text-sky-800 dark:text-sky-200">
            Drop to Capy
          </p>
        </div>
      ) : null}
      <div className="p-3 pt-0">
        <CapyComposer
          client={client}
          session={capy.session}
          health={health}
          value={capy.chat.composer}
          running={capy.chat.runActive}
          chats={chats}
          skills={skills}
          mcpServers={mcpServers}
          modelOptions={modelOptions}
          runtimeSettings={runtimeSettings}
          tokenUsage={capy.chat.tokenUsage}
          captureWindowDrops
          onDropActiveChange={setDropActive}
          onChange={next => capy.setChat(prev => ({ ...prev, composer: next }))}
          onSend={text => {
            if (!text.trim()) return
            void capy.send(text)
          }}
          onStop={() => void capy.stop()}
          onSessionUpdated={next => capy.setSession(next)}
          onMessagesReloaded={() => {
            if (!capy.session) return
            void client.listMessages(capy.session.id).then(messages => {
              capy.setChat(prev => ({
                ...prev,
                messages,
                liveDelta: '',
                tokenUsage: { inputTokens: 0, outputTokens: 0 }
              }))
            })
          }}
          setRuntimeSettings={setRuntimeSettings}
          loadModelOptions={loadModelOptions}
        />
      </div>
      <div
        className="hover:bg-foreground/10 absolute bottom-0 left-0 top-8 z-20 w-1.5 cursor-ew-resize"
        onPointerDown={onResizeDown('w')}
      />
      <div
        className="hover:bg-foreground/10 absolute bottom-0 right-0 top-8 z-20 w-1.5 cursor-ew-resize"
        onPointerDown={onResizeDown('e')}
      />
      <div
        className="hover:bg-foreground/10 absolute bottom-0 left-0 z-20 h-1.5 w-full cursor-ns-resize"
        onPointerDown={onResizeDown('s')}
      />
      <div
        className="absolute bottom-0 left-0 z-30 size-3 cursor-nesw-resize"
        onPointerDown={onResizeDown('sw')}
      />
      <div
        className="absolute bottom-0 right-0 z-30 size-3 cursor-nwse-resize"
        onPointerDown={onResizeDown('se')}
      />
    </div>
  )
}
