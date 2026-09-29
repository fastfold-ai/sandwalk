import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentMessage, AgentPlanCard, AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  type ComponentProps,
  type Dispatch,
  lazy,
  type RefObject,
  type SetStateAction,
  Suspense,
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState
} from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { ChatTranscript } from '@/components/agents/ChatTranscript'
import { DetailPageSkeleton } from '@/components/agents/PageSkeletons'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { startPlanBuild } from '@/lib/plan-build'
import { perfCount } from '@/lib/perf-probe'
import { type SessionChatState } from '@/lib/sessions'
import { cn } from '@/lib/utils'

const InspectView = lazy(() =>
  import('@/components/agents/InspectView').then(m => ({
    default: m.InspectView
  }))
)

export type SessionChatBodyProps = {
  client: LocalAgentClient
  navigate: NavigateFunction
  sessionId: string | null
  session: AgentSession | null
  isInspect: boolean
  messages: AgentMessage[]
  tools: TranscriptTool[]
  messagesLoaded: boolean
  runActive: boolean
  showChatSkeleton: boolean
  agentComposerSlotProps: ComponentProps<typeof AgentComposerSlot>
  projects: AgentProject[]
  recentProjectIds: string[]
  activeProjectId: string | null
  onNewProject: () => void
  selectAllProjects: () => void
  selectProjectScope: (projectId: string) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  chatScrollRef: RefObject<HTMLDivElement | null>
  chatEndRef: RefObject<HTMLDivElement | null>
  conversationTimeline: TranscriptEntry[]
  expandedToolRunKeys: Record<string, boolean>
  patchChat: (
    sessionId: string,
    updater: (prev: SessionChatState) => SessionChatState
  ) => void
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<string, { inputTokens: number; outputTokens: number }>
  copiedMessageId: string | null
  setCopiedMessageId: Dispatch<SetStateAction<string | null>>
  activeRunTools: TranscriptTool[]
  activeRunTodos: import('@sandwalk/agent-ui-core').AgentTodo[]
  activeBuildPlan: import('@sandwalk/agent-ui-core').AgentPlanCard | null
  builtPlanPaths: string[]
  liveDelta: string
  pendingApproval: import('@sandwalk/agent-ui-core').PendingHitlApproval | null
  approvalSubmitting: boolean
  onSubmitApprovals: (
    decisions: import('@sandwalk/agent-ui-core').HitlDecision[]
  ) => void | Promise<void>
  showScrollToBottom: boolean
  scrollChatToBottom: () => void
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
  setPendingOpenPath: Dispatch<SetStateAction<string | null>>
  error: string | null
  /**
   * Split view del panel. `undefined` → chat normal (composer flotante
   * centrado). Cuando existe, el composer pasa a modo "embedded": barra
   * fija al bottom del panel con animación slide up/down según `focused`
   * y el transcript reserva padding-bottom = altura medida del composer.
   */
  splitMode?: { focused: boolean }
}

export function SessionChatBody({
  client,
  navigate,
  sessionId,
  session,
  isInspect,
  messages,
  tools,
  messagesLoaded,
  runActive,
  showChatSkeleton: _showChatSkeleton,
  agentComposerSlotProps,
  projects,
  recentProjectIds,
  activeProjectId,
  onNewProject,
  selectAllProjects,
  selectProjectScope,
  updateSession,
  chatScrollRef,
  chatEndRef,
  conversationTimeline,
  expandedToolRunKeys,
  patchChat,
  runIdByMessageId,
  usageByRunId,
  copiedMessageId,
  setCopiedMessageId,
  activeRunTools,
  activeRunTodos,
  activeBuildPlan,
  builtPlanPaths,
  liveDelta,
  pendingApproval,
  approvalSubmitting,
  onSubmitApprovals,
  showScrollToBottom,
  scrollChatToBottom,
  setFilesPanelCollapsed,
  setPendingOpenPath,
  error,
  splitMode
}: SessionChatBodyProps) {
  perfCount('render.SessionChatBody')
  const isSplit = Boolean(splitMode)
  const splitFocused = splitMode?.focused ?? false
  // Altura medida del composer embedded — el transcript la usa como
  // padding-bottom para que el último mensaje no quede detrás de la barra.
  // ResizeObserver corre solo en modo split; en single-tab el composer sigue
  // en su lugar habitual y no hace falta reservar espacio.
  const composerBarRef = useRef<HTMLDivElement | null>(null)
  const [composerBarHeight, setComposerBarHeight] = useState(0)
  useLayoutEffect(() => {
    if (!isSplit) return
    const el = composerBarRef.current
    if (!el) return
    const update = () => setComposerBarHeight(el.offsetHeight)
    update()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [isSplit])

  // Cuando el panel gana foco en split view, mover el cursor al textarea del
  // composer embedded para que el usuario pueda tipear inmediatamente sin
  // clickear el input. Espera un rAF a que la animación de slide-up arranque
  // así el focus no se pisa con el layout inicial.
  useLayoutEffect(() => {
    if (!isSplit || !splitFocused) return
    const bar = composerBarRef.current
    if (!bar) return
    const raf = window.requestAnimationFrame(() => {
      const ta = bar.querySelector('textarea')
      if (ta instanceof HTMLTextAreaElement) {
        ta.focus({ preventScroll: true })
      }
    })
    return () => window.cancelAnimationFrame(raf)
  }, [isSplit, splitFocused])

  /*
   * "Sticky bottom" en split view: no hace falta lógica local — el hook
   * `useChatScroll` ya tiene memoria por-chat (posición + stickToBottom)
   * y un ResizeObserver que auto-scrollea al bottom cuando LLEGA nuevo
   * contenido con el usuario pegado al bottom. Ese observer fue
   * modificado para NO disparar cuando el viewport solo se achica por
   * cambio de padding (nuestro caso al recuperar focus): solo se activa
   * si el `scrollHeight` REALMENTE creció. Con eso el caso de uso
   * funciona sin pisar la memoria de posición del sistema existente.
   */
  // Stable callbacks: memoized transcript rows must not re-render per stream
  // delta because a lambda got a new identity. Composer props change every
  // render, so reach them through a ref.
  const composerPropsRef = useRef(agentComposerSlotProps)
  composerPropsRef.current = agentComposerSlotProps

  const handleToggleToolRunExpanded = useCallback(
    (key: string) => {
      if (!sessionId) return
      patchChat(sessionId, prev => ({
        ...prev,
        expandedToolRunKeys: {
          ...prev.expandedToolRunKeys,
          [key]: !(prev.expandedToolRunKeys[key] === true)
        }
      }))
    },
    [patchChat, sessionId]
  )

  const handleOpenFile = useCallback(
    (path: string) => {
      setFilesPanelCollapsed(false)
      setPendingOpenPath(path)
    },
    [setFilesPanelCollapsed, setPendingOpenPath]
  )

  const handleBuildPlan = useCallback(
    (plan: AgentPlanCard) => {
      if (!sessionId) return
      void startPlanBuild({
        sessionId,
        plan,
        patchChat,
        client,
        setRuntimeSettings: composerPropsRef.current.setRuntimeSettings,
        handleComposerSend: composerPropsRef.current.handleComposerSend
      })
    },
    [client, patchChat, sessionId]
  )

  const handleInterrupt = useMemo(
    () =>
      sessionId
        ? () => void composerPropsRef.current.handleStop()
        : undefined,
    [sessionId]
  )

  // While hydrating a tab switch, keep the transcript dock (no empty Aura flash).
  // Empty chrome only after load confirms there is no history.
  const hasConversation = messages.length > 0 || runActive
  const showTranscript = hasConversation || !messagesLoaded
  const showEmptyChrome = messagesLoaded && !hasConversation

  // Skip flex morph for one paint when the route session changes.
  const prevSessionRef = useRef(sessionId)
  const [layoutInstant, setLayoutInstant] = useState(false)
  useLayoutEffect(() => {
    if (prevSessionRef.current === sessionId) return
    prevSessionRef.current = sessionId
    setLayoutInstant(true)
    const frame = window.requestAnimationFrame(() => setLayoutInstant(false))
    return () => window.cancelAnimationFrame(frame)
  }, [sessionId])

  return (
    <>
      {isInspect ? (
        <Suspense fallback={<DetailPageSkeleton />}>
          <InspectView
            messages={messages}
            tools={tools}
            onClose={() => navigate(`/agents/${sessionId}`)}
          />
        </Suspense>
      ) : null}
      <div
        className={cn(
          'relative flex min-h-0 flex-1 flex-col',
          isInspect && 'hidden'
        )}
      >
        <div
          className={cn(
            'flex min-h-0 flex-col overflow-hidden',
            !layoutInstant &&
              'transition-[flex-grow,opacity,padding-bottom] duration-500 ease-out',
            // En split, el padding-bottom se anima a 300 ms — mismo timing
            // que el slide del composer — para que ambos movimientos se
            // vean como uno solo.
            isSplit && !layoutInstant && 'transition-[padding-bottom] duration-300 ease-out'
          )}
          style={{
            flexGrow: showTranscript ? 1 : 0,
            flexShrink: 1,
            flexBasis: 0,
            opacity: showTranscript ? 1 : 0,
            /*
             * En modo split reservamos el hueco del composer SOLO cuando el
             * panel está focused. Cuando pierde focus el composer se
             * desliza hacia abajo (translate-y-full + opacity 0), y con
             * padding-bottom en 0 el transcript ocupa todo el alto del
             * panel — sin dejar el hueco negro vacío donde vivía el
             * composer. Los dos paneles del split cambian al unísono.
             */
            paddingBottom: isSplit
              ? splitFocused
                ? composerBarHeight
                : 0
              : undefined
          }}
        >
          {showTranscript ? (
            <ChatTranscript
              key={sessionId ?? 'no-session'}
              chatScrollRef={chatScrollRef}
              chatEndRef={chatEndRef}
              conversationTimeline={conversationTimeline}
              expandedToolRunKeys={expandedToolRunKeys}
              sessionId={sessionId}
              client={client}
              onToggleToolRunExpanded={handleToggleToolRunExpanded}
              runActive={runActive}
              tools={tools}
              runIdByMessageId={runIdByMessageId}
              usageByRunId={usageByRunId}
              messages={messages}
              copiedMessageId={copiedMessageId}
              setCopiedMessageId={setCopiedMessageId}
              session={session}
              onOpenFile={handleOpenFile}
              onBuildPlan={handleBuildPlan}
              onInterrupt={handleInterrupt}
              activeRunTools={activeRunTools}
              activeRunTodos={activeRunTodos}
              activeBuildPlan={activeBuildPlan}
              builtPlanPaths={builtPlanPaths}
              liveDelta={liveDelta}
              pendingApproval={pendingApproval}
              approvalSubmitting={approvalSubmitting}
              onSubmitApprovals={onSubmitApprovals}
              showScrollToBottom={showScrollToBottom}
              onScrollToBottom={scrollChatToBottom}
              skills={agentComposerSlotProps.skills}
              mcpServers={agentComposerSlotProps.mcpServers}
              workspaceFiles={agentComposerSlotProps.workspaceFiles}
            />
          ) : null}
        </div>

        {isSplit ? (
          /*
           * Composer embedded del split view.
           *
           * `absolute inset-x-0 bottom-0`  → barra fija abajo, ancho completo
           *                                  del panel, sin gutter lateral.
           * `bg-background border-t`       → banda opaca separada del
           *                                  transcript por 1 px del color
           *                                  del border del panel.
           * `translate-y-full opacity-0`   → cuando el panel no está en focus,
           *                                  la barra se desliza hacia abajo
           *                                  y desaparece (300 ms ease-out).
           * `pointer-events-none`          → mientras está oculta, no captura
           *                                  clicks (el composer sigue montado
           *                                  para preservar el texto).
           *
           * El composer permanece montado siempre — solo se oculta visual y
           * funcionalmente. Al volver el focus reaparece con el mismo texto,
           * chips y estado de IME.
           */
          <div
            ref={composerBarRef}
            data-composer-slot
            className={cn(
              /*
               * `inset-x-0 bottom-0`: la barra ES la parte inferior del
               * panel. Cero padding: sin gutter lateral, sin banda vacía
               * arriba/abajo. El único separador visual con el transcript
               * es el `border-t border-border/50`. Las esquinas curvas
               * inferiores las hereda del `rounded-lg` del panel gracias
               * al `overflow-hidden` del ChatTilingContainer.
               */
              'bg-muted/40 border-border/50 absolute inset-x-0 bottom-0 z-10 border-t will-change-transform',
              'transition-[transform,opacity] duration-300 ease-out',
              splitFocused
                ? 'translate-y-0 opacity-100'
                : 'pointer-events-none translate-y-full opacity-0'
            )}
          >
            <AgentComposerSlot
              {...agentComposerSlotProps}
              embedded
              /*
               * Solo el panel focused del split autoenfoca su composer. Si
               * los N paneles compitieran por el foco al montar, el último
               * en autoenfocarse dispararía `onFocusCapture` del panel
               * padre en `ChatTilingContainer`, llamando `onFocusChat` con
               * el chatId equivocado — pisando la selección que el usuario
               * hizo desde el sidebar (o desde otro punto).
               */
              autoFocus={splitFocused}
            />
          </div>
        ) : (
          <div
            className={cn(
              'bg-background mx-auto flex w-full max-w-[44rem] flex-col px-5',
              !layoutInstant &&
                'transition-[flex-grow,padding] duration-500 ease-out',
              showEmptyChrome ? 'justify-center' : 'justify-end'
            )}
            style={{
              flexGrow: showEmptyChrome ? 1 : 0,
              flexShrink: 0,
              flexBasis: 'auto',
              paddingBottom: showEmptyChrome ? '5rem' : '1.5rem',
              paddingTop: showEmptyChrome ? 0 : '0.5rem'
            }}
          >
            <div
              className={cn(
                'flex flex-col items-center overflow-hidden',
                !layoutInstant &&
                  'transition-[max-height,opacity,margin] duration-300 ease-out',
                showEmptyChrome
                  ? 'mb-2 max-h-40 opacity-100'
                  : 'mb-0 max-h-0 opacity-0'
              )}
            >
              <AuraIconPulse className="text-muted-foreground/70 mb-6 h-12 w-12" />
              <div className="mb-2 flex w-full items-center px-1">
                <ProjectPicker
                  projects={projects}
                  value={session?.projectId ?? activeProjectId}
                  recentIds={recentProjectIds}
                  noneLabel="All"
                  onNewProject={onNewProject}
                  onChange={projectId => {
                    if (session) {
                      void updateSession(session, { projectId })
                    }
                    if (projectId) selectProjectScope(projectId)
                    else selectAllProjects()
                  }}
                />
              </div>
            </div>
            <AgentComposerSlot {...agentComposerSlotProps} />
          </div>
        )}
      </div>
      {error ? (
        <div className="bg-destructive text-destructive-foreground absolute bottom-2 left-1/2 -translate-x-1/2 rounded-md px-3 py-1.5 text-xs">
          {error}
        </div>
      ) : null}
    </>
  )
}
