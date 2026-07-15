import '@xterm/xterm/css/xterm.css'

import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { PtySessionInfo } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  readTerminalTabColors,
  writeTerminalTabColors
} from './terminal-tab-colors'
import { TerminalTabBar } from './terminal-tab-bar'
import { TerminalTabContextMenu } from './terminal-tab-context-menu'
import { TerminalViewport } from './terminal-viewport'
import { useTerminalLive } from './use-terminal-live'

type TerminalPanelProps = {
  client: LocalAgentClient
  sessionId: string
  visible?: boolean
  autoCreateOnEmpty?: boolean
  startupCommand?: string | null
  startupNonce?: number
  onClose?: () => void
}

export function TerminalPanel({
  client,
  sessionId,
  visible = true,
  autoCreateOnEmpty = false,
  startupCommand = null,
  startupNonce = 0,
  onClose
}: TerminalPanelProps) {
  const [tabs, setTabs] = useState<PtySessionInfo[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [booting, setBooting] = useState(true)
  const [tabColors, setTabColors] = useState<Record<string, string>>(() =>
    readTerminalTabColors(sessionId)
  )
  const [tabMenu, setTabMenu] = useState<{
    id: string
    x: number
    y: number
  } | null>(null)
  const [renameId, setRenameId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [renameBusy, setRenameBusy] = useState(false)
  const renameCancelRef = useRef(false)
  const renameIgnoreBlurRef = useRef(false)
  const renameBusyRef = useRef(false)
  const renameIdRef = useRef<string | null>(null)
  const renameValueRef = useRef('')
  const renameInputRef = useRef<HTMLInputElement | null>(null)
  const creatingRef = useRef(false)
  const lastStartupNonceRef = useRef<number>(-1)
  renameIdRef.current = renameId
  renameValueRef.current = renameValue
  renameBusyRef.current = renameBusy

  const {
    hostsRef,
    livesRef,
    connectLive,
    disposeLive,
    disposeAll,
    mountActive,
    sendCommandToLive
  } = useTerminalLive({ client, sessionId, renameIdRef })

  useEffect(() => {
    setTabColors(readTerminalTabColors(sessionId))
  }, [sessionId])

  const beginRename = useCallback((tab: PtySessionInfo) => {
    renameCancelRef.current = false
    renameIgnoreBlurRef.current = true
    setActiveId(tab.id)
    setRenameId(tab.id)
    setRenameValue(tab.title)
    requestAnimationFrame(() => {
      renameInputRef.current?.focus()
      renameInputRef.current?.select()
      window.setTimeout(() => {
        renameIgnoreBlurRef.current = false
      }, 150)
    })
  }, [])

  const cancelRename = useCallback(() => {
    renameCancelRef.current = true
    setRenameId(null)
    setRenameValue('')
  }, [])

  const setTabColor = useCallback(
    (ptyId: string, color: string | null) => {
      setTabColors(current => {
        const next = { ...current }
        if (color) next[ptyId] = color
        else delete next[ptyId]
        writeTerminalTabColors(sessionId, next)
        return next
      })
    },
    [sessionId]
  )

  const createTab = useCallback(async () => {
    if (creatingRef.current) return
    creatingRef.current = true
    setStatus(null)
    try {
      const info = await client.createPtySession(sessionId)
      connectLive(info)
      setTabs(current => [...current, info])
      setActiveId(info.id)
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : 'Failed to create terminal'
      )
    } finally {
      creatingRef.current = false
    }
  }, [client, connectLive, sessionId])

  const closeTab = useCallback(
    async (ptyId: string) => {
      disposeLive(ptyId)
      setTabs(current => {
        const next = current.filter(tab => tab.id !== ptyId)
        setActiveId(active => {
          if (active !== ptyId) return active
          return next.at(-1)?.id || null
        })
        return next
      })
      setTabColor(ptyId, null)
      try {
        await client.deletePtySession(sessionId, ptyId)
      } catch {
        // ignore remote cleanup failures
      }
    },
    [client, disposeLive, sessionId, setTabColor]
  )

  const submitRename = useCallback(async () => {
    const ptyId = renameIdRef.current
    const title = renameValueRef.current.trim()
    if (!ptyId || !title || renameBusyRef.current) return
    const current = tabs.find(tab => tab.id === ptyId)
    if (current && current.title === title) {
      setRenameId(null)
      setRenameValue('')
      return
    }
    renameBusyRef.current = true
    setRenameBusy(true)
    setStatus(null)
    setTabs(currentTabs =>
      currentTabs.map(tab => (tab.id === ptyId ? { ...tab, title } : tab))
    )
    setRenameId(null)
    setRenameValue('')
    try {
      const updated = await client.updatePtySession(sessionId, ptyId, {
        title
      })
      setTabs(currentTabs =>
        currentTabs.map(tab => (tab.id === ptyId ? { ...tab, ...updated } : tab))
      )
      const live = livesRef.current[ptyId]
      if (live && !live.disposed) live.info = { ...live.info, ...updated }
    } catch (error) {
      if (current) {
        setTabs(currentTabs =>
          currentTabs.map(tab =>
            tab.id === ptyId ? { ...tab, title: current.title } : tab
          )
        )
      }
      setStatus(
        error instanceof Error ? error.message : 'Failed to rename terminal'
      )
    } finally {
      renameBusyRef.current = false
      setRenameBusy(false)
    }
  }, [client, livesRef, sessionId, tabs])

  const commitRenameFromBlur = useCallback(() => {
    if (renameBusyRef.current || renameIgnoreBlurRef.current) return
    if (renameCancelRef.current) {
      renameCancelRef.current = false
      return
    }
    const ptyId = renameIdRef.current
    const title = renameValueRef.current.trim()
    const current = ptyId ? tabs.find(tab => tab.id === ptyId) : null
    if (title && current && title !== current.title) {
      void submitRename()
    } else {
      setRenameId(null)
      setRenameValue('')
    }
  }, [submitRename, tabs])

  useEffect(() => {
    let cancelled = false
    setBooting(true)
    setStatus(null)
    ;(async () => {
      try {
        const existing = await client.listPtySessions(sessionId)
        if (cancelled) return
        for (const info of existing) connectLive(info)
        setTabs(existing)
        const firstId = existing[0]?.id || null
        setActiveId(firstId)
        if (existing.length === 0 && autoCreateOnEmpty) {
          void createTab()
        }
      } catch (error) {
        if (!cancelled) {
          setStatus(
            error instanceof Error ? error.message : 'Failed to start terminal'
          )
        }
      } finally {
        if (!cancelled) setBooting(false)
      }
    })()

    return () => {
      cancelled = true
      disposeAll()
    }
  }, [autoCreateOnEmpty, client, connectLive, createTab, disposeAll, sessionId])

  useEffect(() => {
    mountActive(activeId)
  }, [activeId, mountActive, tabs])

  useEffect(() => {
    if (!visible || !activeId) return
    requestAnimationFrame(() => mountActive(activeId))
  }, [visible, activeId, mountActive])

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
    <div className="bg-card border-border flex h-full min-h-0 flex-col border-t">
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
        onMountActive={mountActive}
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
