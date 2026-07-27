import '@xterm/xterm/css/xterm.css'

import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useEffect, useRef } from 'react'

import { cn } from '@/lib/utils'

import { TerminalTabBar } from './terminal-tab-bar'
import { TerminalTabContextMenu } from './terminal-tab-context-menu'
import { TerminalViewport } from './terminal-viewport'
import { useTerminalPanelTabs } from './use-terminal-panel-tabs'

type TerminalPanelProps = {
  client: LocalAgentClient
  sessionId: string
  visible?: boolean
  autoCreateOnEmpty?: boolean
  startupCommand?: string | null
  startupNonce?: number
  onClose?: () => void
  className?: string
}

export function TerminalPanel({
  client,
  sessionId,
  visible = true,
  autoCreateOnEmpty = false,
  startupCommand = null,
  startupNonce = 0,
  onClose,
  className
}: TerminalPanelProps) {
  const lastStartupNonceRef = useRef<number>(-1)

  const {
    tabs,
    activeId,
    setActiveId,
    status,
    booting,
    tabColors,
    tabMenu,
    setTabMenu,
    renameId,
    renameValue,
    setRenameValue,
    renameInputRef,
    renameIgnoreBlurRef,
    hostsRef,
    beginRename,
    cancelRename,
    setTabColor,
    createTab,
    closeTab,
    submitRename,
    commitRenameFromBlur,
    mountActive,
    livesRef,
    sendCommandToLive
  } = useTerminalPanelTabs({ client, sessionId, autoCreateOnEmpty })

  useEffect(() => {
    if (booting) return
    mountActive(activeId)
  }, [activeId, booting, mountActive, tabs])

  useEffect(() => {
    if (!visible || !activeId || booting) return
    requestAnimationFrame(() => mountActive(activeId))
  }, [visible, activeId, booting, mountActive])

  useEffect(() => {
    if (!activeId) return
    const onResize = () => mountActive(activeId)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [activeId, mountActive])

  useEffect(() => {
    const command = String(startupCommand || '').trim()
    if (!command) return
    if (startupNonce <= 0) return
    if (lastStartupNonceRef.current === startupNonce) return
    const targetId = activeId || tabs[0]?.id
    if (!targetId) return
    const live = livesRef.current[targetId]
    if (!live || live.disposed) return
    sendCommandToLive(live, command)
    lastStartupNonceRef.current = startupNonce
  }, [activeId, livesRef, sendCommandToLive, startupCommand, startupNonce, tabs])

  return (
    <div
      className={cn(
        'bg-card border-border flex h-full min-h-0 flex-col border-t',
        className
      )}
    >
      <TerminalTabBar
        tabs={tabs}
        activeId={activeId}
        tabColors={tabColors}
        renameId={renameId}
        renameValue={renameValue}
        renameInputRef={renameInputRef}
        renameIgnoreBlurRef={renameIgnoreBlurRef}
        onSelectTab={setActiveId}
        onCloseTab={closeTab}
        onBeginRename={beginRename}
        onRenameValueChange={setRenameValue}
        onSubmitRename={() => void submitRename()}
        onCancelRename={cancelRename}
        onCommitRenameFromBlur={commitRenameFromBlur}
        onTabContextMenu={(id, x, y) => setTabMenu({ id, x, y })}
        onCreateTab={() => void createTab()}
        onClose={onClose}
      />

      <TerminalViewport
        booting={booting}
        status={status}
        tabs={tabs}
        activeId={activeId}
        hostsRef={hostsRef}
        onCreateTab={() => void createTab()}
      />

      <TerminalTabContextMenu
        menu={tabMenu}
        tabs={tabs}
        tabColors={tabColors}
        onClose={() => setTabMenu(null)}
        onRename={beginRename}
        onSetTabColor={setTabColor}
        onTerminate={closeTab}
      />
    </div>
  )
}
