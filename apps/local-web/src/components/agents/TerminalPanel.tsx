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
  /**
   * FAS-107 Q3: when true, hide the internal tab-bar + "New terminal"
   * button. The panel then behaves as a single-shell viewport, which is
   * what terminal-as-first-class needs (each terminal instance owns its
   * own PTY; sub-tabs are legacy from the pre-FAS-107 side-panel).
   *
   * Default is false to preserve the multi-shell tool-window usage
   * (WorkspacePanel side-panel, integrations, onboarding).
   */
  singleShell?: boolean
}

export function TerminalPanel({
  client,
  sessionId,
  visible = true,
  autoCreateOnEmpty = false,
  startupCommand = null,
  startupNonce = 0,
  onClose,
  className,
  singleShell = false
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

  // Observe the terminal host DOM directly so pane resizes (dragging a
  // split divider) refit xterm and inform the PTY of the new cols/rows.
  // `window.resize` above only fires when the whole window changes; when
  // the terminal lives inside a split, its own size can change without
  // any window event, and xterm keeps the stale 80x24 buffer — the PTY
  // then wraps its output at a column count the pane can't show, which
  // is the letter-per-line rendering bug users see after any drag.
  // Precedent: this is the pattern documented by xterm.js and used by
  // VSCode's terminal wrapper and Warp.
  useEffect(() => {
    if (!activeId) return
    const host = hostsRef.current[activeId]
    if (!host) return
    if (typeof ResizeObserver === 'undefined') return
    let rafId: number | null = null
    const observer = new ResizeObserver(() => {
      // Debounce with rAF: the observer fires many times per frame while
      // the user drags a divider — one refit per frame is enough and
      // avoids spamming `updatePtySession` on every intermediate size.
      if (rafId != null) return
      rafId = window.requestAnimationFrame(() => {
        rafId = null
        mountActive(activeId)
      })
    })
    observer.observe(host)
    return () => {
      observer.disconnect()
      if (rafId != null) window.cancelAnimationFrame(rafId)
    }
  }, [activeId, mountActive, hostsRef])

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
      {/* FAS-107 Q3: single-shell mode hides the internal tab bar. The
          rename / context menu / delete actions viven ahora en el
          header del panel del split (TerminalSplitPanelHeader) o en
          el sidebar row. Los sub-tabs sólo aplican al legacy multi-
          shell mode. */}
      {singleShell ? null : (
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
      )}

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
