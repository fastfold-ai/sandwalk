import '@xterm/xterm/css/xterm.css'

import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { PtySessionInfo } from '@sandwalk/agent-ui-core'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal as XTerm } from '@xterm/xterm'
import {
  Pencil,
  Plus,
  SquareTerminal,
  Trash2,
  X
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  buildTerminalTheme,
  isDocumentDark,
  watchTerminalTheme
} from '@/lib/terminal-theme'
import { cn } from '@/lib/utils'

import {
  tabColorBackgroundStyle,
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator,
  TabInlineColorRow
} from './tab-context-menu'

type TerminalPanelProps = {
  client: LocalAgentClient
  sessionId: string
  visible?: boolean
  autoCreateOnEmpty?: boolean
  startupCommand?: string | null
  startupNonce?: number
  onClose?: () => void
}

type LiveTerminal = {
  info: PtySessionInfo
  term: XTerm
  fit: FitAddon
  socket: WebSocket | null
  container: HTMLDivElement | null
  disposed: boolean
  opened: boolean
}

const TERMINAL_TAB_COLORS_KEY = 'fastfold.terminal-tab-colors'

function readTerminalTabColors(sessionId: string): Record<string, string> {
  try {
    const raw = localStorage.getItem(TERMINAL_TAB_COLORS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, Record<string, string>>
    const entry = parsed?.[sessionId]
    if (!entry || typeof entry !== 'object') return {}
    return Object.fromEntries(
      Object.entries(entry).filter(
        ([id, color]) =>
          typeof id === 'string' &&
          typeof color === 'string' &&
          color.length > 0
      )
    )
  } catch {
    return {}
  }
}

function writeTerminalTabColors(
  sessionId: string,
  colors: Record<string, string>
) {
  try {
    const raw = localStorage.getItem(TERMINAL_TAB_COLORS_KEY)
    const parsed = raw
      ? (JSON.parse(raw) as Record<string, Record<string, string>>)
      : {}
    parsed[sessionId] = colors
    localStorage.setItem(TERMINAL_TAB_COLORS_KEY, JSON.stringify(parsed))
  } catch {
    // ignore storage failures
  }
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
  const hostsRef = useRef<Record<string, HTMLDivElement | null>>({})
  const livesRef = useRef<Record<string, LiveTerminal>>({})
  const creatingRef = useRef(false)
  const darkRef = useRef(isDocumentDark())
  const lastStartupNonceRef = useRef<number>(-1)
  renameIdRef.current = renameId
  renameValueRef.current = renameValue
  renameBusyRef.current = renameBusy

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

  useEffect(() => {
    const apply = () => {
      const nextDark = isDocumentDark()
      darkRef.current = nextDark
      const next = buildTerminalTheme(nextDark)
      for (const live of Object.values(livesRef.current)) {
        if (live.disposed) continue
        live.term.options.theme = next
      }
    }
    apply()
    return watchTerminalTheme(apply)
  }, [])

  const disposeLive = useCallback((ptyId: string) => {
    const live = livesRef.current[ptyId]
    if (!live || live.disposed) return
    live.disposed = true
    try {
      live.socket?.close()
    } catch {
      // ignore
    }
    try {
      live.term.dispose()
    } catch {
      // ignore
    }
    delete livesRef.current[ptyId]
  }, [])

  const connectLive = useCallback(
    (info: PtySessionInfo) => {
      if (livesRef.current[info.id] && !livesRef.current[info.id].disposed) {
        return livesRef.current[info.id]
      }
      const term = new XTerm({
        cursorBlink: true,
        cursorStyle: 'bar',
        fontSize: 12.5,
        lineHeight: 1.35,
        letterSpacing: 0,
        fontFamily:
          '"SF Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        theme: buildTerminalTheme(darkRef.current),
        convertEol: true,
        allowTransparency: false,
        scrollback: 5000,
        smoothScrollDuration: 0
      })
      // Keep browser chrome from stealing nano/vim Ctrl shortcuts while focused.
      term.attachCustomKeyEventHandler(event => {
        if (event.type !== 'keydown') return true
        const key = event.key.toLowerCase()

        // Cmd/Ctrl+Shift+C → copy selection (don't send ^C to the PTY)
        if (
          event.shiftKey &&
          key === 'c' &&
          (event.metaKey || event.ctrlKey) &&
          term.hasSelection()
        ) {
          void navigator.clipboard.writeText(term.getSelection())
          return false
        }

        // Prefer Control (not Cmd) for terminal apps like nano: ^O ^X ^G ^W …
        if (event.ctrlKey && !event.metaKey && !event.altKey) {
          if (
            (key.length === 1 && /[a-z0-9[\];',./\\=-`]/.test(key)) ||
            [
              'backspace',
              'delete',
              'enter',
              'tab',
              'arrowup',
              'arrowdown',
              'arrowleft',
              'arrowright',
              'home',
              'end',
              'pageup',
              'pagedown'
            ].includes(key)
          ) {
            event.preventDefault()
          }
        }

        // Block Cmd+W from closing the browser tab while typing in the terminal
        if (event.metaKey && !event.altKey && key === 'w') {
          event.preventDefault()
        }

        return true
      })
      const fit = new FitAddon()
      term.loadAddon(fit)
      const live: LiveTerminal = {
        info,
        term,
        fit,
        socket: null,
        container: null,
        disposed: false,
        opened: false
      }
      livesRef.current[info.id] = live

      live.term.onData(data => {
        if (live.socket?.readyState === WebSocket.OPEN) {
          live.socket.send(data)
        }
      })

      live.term.onResize(({ cols, rows }) => {
        void client.updatePtySession(sessionId, info.id, { cols, rows })
      })

      return live
    },
    [client, sessionId]
  )

  const ensureSocket = useCallback(
    (live: LiveTerminal) => {
      if (live.disposed || live.socket) return
      const socket = new WebSocket(
        client.ptyConnectUrl(sessionId, live.info.id)
      )
      socket.binaryType = 'arraybuffer'
      live.socket = socket

      socket.addEventListener('open', () => {
        if (live.disposed) return
        try {
          live.fit.fit()
          const dims = live.fit.proposeDimensions()
          if (dims) {
            void client.updatePtySession(sessionId, live.info.id, {
              cols: dims.cols,
              rows: dims.rows
            })
          }
        } catch {
          // ignore fit failures
        }
        // Reconnecting to a live shell often has an empty viewport (prompt
        // already printed server-side). Ctrl+L clears + redraws zsh/bash prompt.
        window.setTimeout(() => {
          if (live.disposed || live.socket?.readyState !== WebSocket.OPEN) return
          const line = live.term.buffer.active.getLine(0)
          const text = line?.translateToString(true).trim() ?? ''
          if (!text) {
            live.socket.send('\x0c')
          }
        }, 80)
      })

      socket.addEventListener('message', event => {
        if (live.disposed) return
        if (typeof event.data === 'string') {
          live.term.write(event.data)
          return
        }
        live.term.write(new Uint8Array(event.data as ArrayBuffer))
      })

      socket.addEventListener('close', () => {
        if (live.disposed) return
        live.term.writeln('\r\n\x1b[90m[terminal disconnected]\x1b[0m')
      })
    },
    [client, sessionId]
  )

  const mountActive = useCallback(
    (ptyId: string | null) => {
      if (!ptyId) return
      const host = hostsRef.current[ptyId]
      const live = livesRef.current[ptyId]
      if (!host || !live || live.disposed) return
      // Open xterm BEFORE connecting the PTY socket so cursor-position
      // queries from zsh get answered and the prompt can render.
      if (!live.opened) {
        host.replaceChildren()
        live.term.open(host)
        live.container = host
        live.opened = true
      }
      ensureSocket(live)
      requestAnimationFrame(() => {
        try {
          live.fit.fit()
          // Don't steal focus while the user is renaming a tab.
          if (!renameIdRef.current) {
            live.term.focus()
          }
          const dims = live.fit.proposeDimensions()
          if (dims && live.socket?.readyState === WebSocket.OPEN) {
            void client.updatePtySession(sessionId, live.info.id, {
              cols: dims.cols,
              rows: dims.rows
            })
          }
        } catch {
          // ignore
        }
      })
    },
    [client, ensureSocket, sessionId]
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

  const sendCommandToLive = useCallback(
    (live: LiveTerminal, command: string) => {
      const payload = command.endsWith('\n') ? command : `${command}\n`
      const send = () => {
        if (live.disposed) return
        if (live.socket?.readyState === WebSocket.OPEN) {
          live.socket.send(payload)
        }
      }
      if (live.socket?.readyState === WebSocket.OPEN) {
        send()
        return
      }
      ensureSocket(live)
      const socket = live.socket
      if (!socket) return
      if (socket.readyState === WebSocket.OPEN) {
        send()
        return
      }
      const onOpen = () => {
        socket.removeEventListener('open', onOpen)
        send()
      }
      socket.addEventListener('open', onOpen)
    },
    [ensureSocket]
  )

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
    // Optimistic local update so the tab label changes immediately.
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
  }, [client, sessionId, tabs])

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
      for (const ptyId of Object.keys(livesRef.current)) {
        disposeLive(ptyId)
      }
    }
  }, [autoCreateOnEmpty, client, connectLive, createTab, disposeLive, sessionId])

  useEffect(() => {
    mountActive(activeId)
  }, [activeId, mountActive, tabs])

  useEffect(() => {
    if (!visible || !activeId) return
    // Panel was collapsed; refit and refocus when shown again.
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
  }, [activeId, sendCommandToLive, startupCommand, startupNonce, tabs])

  return (
    <div className="bg-card border-border flex h-full min-h-0 flex-col border-t">
      <div className="flex h-10 shrink-0 items-center gap-1 px-1.5">
        <div className="chat-scrollbar-x flex min-w-0 flex-1 items-stretch gap-0.5 overflow-x-auto">
          {tabs.map(tab => {
            const color = tabColors[tab.id]
            const renaming = renameId === tab.id
            const colored = Boolean(color)
            return (
              <div
                key={tab.id}
                className={cn(
                  'group relative my-auto flex h-8 max-w-[180px] shrink-0 items-center rounded-md px-2.5',
                  colored
                    ? 'text-[#1f2937]'
                    : activeId === tab.id || renaming
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                  colored &&
                    activeId !== tab.id &&
                    !renaming &&
                    'opacity-90 hover:opacity-100',
                  renaming && 'max-w-[220px] pr-1.5'
                )}
                style={color ? tabColorBackgroundStyle(color) : undefined}
                onContextMenu={event => {
                  if (renaming) return
                  event.preventDefault()
                  setTabMenu({
                    id: tab.id,
                    x: event.clientX,
                    y: event.clientY
                  })
                }}
              >
                {renaming ? (
                  <div className="inline-flex min-w-0 max-w-full flex-1 items-center gap-1.5">
                    <span
                      className={cn(
                        'inline-flex size-5 shrink-0 items-center justify-center rounded-full',
                        colored ? 'bg-black/15' : 'bg-transparent'
                      )}
                    >
                      <SquareTerminal className="size-3.5 opacity-80" />
                    </span>
                    <input
                      ref={renameInputRef}
                      className={cn(
                        'border-input bg-background text-foreground focus-visible:ring-ring h-6 w-full min-w-[6rem] rounded border px-1.5 text-xs font-medium outline-none focus-visible:ring-1',
                        colored &&
                          'border-black/15 bg-white/70 text-[#1f2937] focus-visible:ring-black/20'
                      )}
                      value={renameValue}
                      onFocus={event => event.currentTarget.select()}
                      onChange={event => setRenameValue(event.target.value)}
                      onClick={event => event.stopPropagation()}
                      onKeyDown={event => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          event.stopPropagation()
                          renameIgnoreBlurRef.current = true
                          void submitRename()
                        } else if (event.key === 'Escape') {
                          event.preventDefault()
                          event.stopPropagation()
                          cancelRename()
                        }
                      }}
                      onBlur={() => commitRenameFromBlur()}
                    />
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      className="inline-flex min-w-0 max-w-full items-center gap-1.5 truncate pr-0 text-left text-xs font-medium"
                      title={tab.title}
                      onClick={() => setActiveId(tab.id)}
                      onDoubleClick={event => {
                        event.preventDefault()
                        beginRename(tab)
                      }}
                    >
                      <span
                        className={cn(
                          'inline-flex size-5 shrink-0 items-center justify-center rounded-full',
                          colored ? 'bg-black/15' : 'bg-transparent'
                        )}
                      >
                        <SquareTerminal className="size-3.5 opacity-80" />
                      </span>
                      <span className="truncate">{tab.title}</span>
                    </button>
                    <button
                      type="button"
                      className={cn(
                        'absolute right-0.5 top-1/2 inline-flex size-5 -translate-y-1/2 items-center justify-center rounded-sm opacity-0 group-hover:opacity-100',
                        colored
                          ? 'bg-black/10 hover:bg-black/20'
                          : 'bg-muted hover:bg-background/80'
                      )}
                      aria-label={`Close ${tab.title}`}
                      onClick={event => {
                        event.stopPropagation()
                        void closeTab(tab.id)
                      }}
                    >
                      <X className="size-3.5" />
                    </button>
                  </>
                )}
              </div>
            )
          })}
        </div>
        <div className="ml-auto flex shrink-0 items-center">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-foreground size-7"
            title="New terminal"
            aria-label="New terminal"
            onClick={() => void createTab()}
          >
            <Plus className="size-3.5" />
          </Button>
          {onClose ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-foreground size-7"
              title="Hide terminal"
              aria-label="Hide terminal"
              onClick={onClose}
            >
              <X className="size-3.5" />
            </Button>
          ) : null}
        </div>
      </div>

      <div className="relative min-h-0 flex-1">
        {booting ? (
          <div className="text-muted-foreground absolute inset-0 flex items-center justify-center text-xs">
            Starting terminal…
          </div>
        ) : status && tabs.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
            <p className="text-destructive text-xs">{status}</p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={() => void createTab()}
            >
              Retry
            </Button>
          </div>
        ) : tabs.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
            <p className="text-muted-foreground text-xs">No terminals open</p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={() => void createTab()}
            >
              <Plus className="mr-1 size-3.5" />
              New terminal
            </Button>
          </div>
        ) : (
          tabs.map(tab => (
            <div
              key={tab.id}
              className={cn(
                'absolute inset-0 overflow-hidden px-2 pb-2 pt-0.5 [&_.xterm]:h-full [&_.xterm-viewport]:!overflow-auto',
                activeId === tab.id ? 'block' : 'hidden'
              )}
              ref={node => {
                hostsRef.current[tab.id] = node
                if (activeId === tab.id) mountActive(tab.id)
              }}
            />
          ))
        )}
      </div>

      {tabMenu && tabs.some(tab => tab.id === tabMenu.id) ? (
        <TabContextMenuShell
          x={tabMenu.x}
          y={tabMenu.y}
          onClose={() => setTabMenu(null)}
        >
          <TabContextItem
            icon={<Pencil className="size-3.5" />}
            label="Rename…"
            onClick={() => {
              const tab = tabs.find(item => item.id === tabMenu.id)
              setTabMenu(null)
              if (!tab) return
              beginRename(tab)
            }}
          />
          <TabContextSeparator />
          <TabInlineColorRow
            value={tabColors[tabMenu.id] || null}
            onSelect={color => {
              setTabColor(tabMenu.id, color)
              setTabMenu(null)
            }}
            onClear={() => {
              setTabColor(tabMenu.id, null)
              setTabMenu(null)
            }}
          />
          <TabContextSeparator />
          <TabContextItem
            icon={<Trash2 className="size-3.5" />}
            label="Terminate"
            destructive
            onClick={() => {
              const id = tabMenu.id
              setTabMenu(null)
              void closeTab(id)
            }}
          />
        </TabContextMenuShell>
      ) : null}
    </div>
  )
}
