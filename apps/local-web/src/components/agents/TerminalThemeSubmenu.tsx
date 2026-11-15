import { Check, ClipboardPaste, Palette } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import {
  SplitDownIcon,
  SplitLeftIcon,
  SplitRightIcon,
  SplitUpIcon
} from '@/components/agents/split-icons'
import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator,
  TabContextSubmenu
} from '@/components/agents/tab-context-menu'
import type { PaneSplitDirection } from '@/lib/pane-split'
import {
  getTerminalScheme,
  requestTerminalPaste,
  setTerminalScheme,
  TERMINAL_SCHEMES,
  TERMINAL_SURFACE_MENU_EVENT,
  TERMINAL_THEME_EVENT,
  type TerminalSchemeId
} from '@/lib/terminal-theme'

function useTerminalScheme(): TerminalSchemeId {
  const [scheme, setScheme] = useState(getTerminalScheme)
  useEffect(() => {
    const sync = () => setScheme(getTerminalScheme())
    window.addEventListener(TERMINAL_THEME_EVENT, sync)
    return () => window.removeEventListener(TERMINAL_THEME_EVENT, sync)
  }, [])
  return scheme
}

export function TerminalThemeItems({ onDone }: { onDone?: () => void }) {
  const scheme = useTerminalScheme()
  return (
    <>
      {TERMINAL_SCHEMES.map(option => {
        const selected = option.id === scheme
        return (
          <button
            key={option.id}
            type="button"
            role="menuitemradio"
            aria-checked={selected}
            className="hover:bg-muted flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-xs"
            onMouseDown={event => event.preventDefault()}
            onClick={event => {
              event.preventDefault()
              event.stopPropagation()
              setTerminalScheme(option.id)
              onDone?.()
            }}
          >
            <span className="min-w-0 flex-1 truncate">{option.label}</span>
            {selected ? <Check className="size-3 shrink-0" /> : null}
          </button>
        )
      })}
    </>
  )
}

/** Nested row for tab, sidebar, pane, and terminal surface menus. */
export function TerminalThemeSubmenu({ onDone }: { onDone?: () => void }) {
  return (
    <TabContextSubmenu icon={<Palette />} label="Terminal theme">
      <TerminalThemeItems onDone={onDone} />
    </TabContextSubmenu>
  )
}

type SurfaceMenuState = {
  x: number
  y: number
  terminalId: string
}

/**
 * Right-click on the terminal. Same shape as a Warp context menu:
 * paste, then theme as a submenu, then split directions.
 */
export function TerminalSurfaceContextMenu({
  onSplitPane
}: {
  onSplitPane: (
    terminalId: string,
    direction: PaneSplitDirection,
    side: 'before' | 'after'
  ) => void
}) {
  const [state, setState] = useState<SurfaceMenuState | null>(null)
  const close = useCallback(() => setState(null), [])

  useEffect(() => {
    const open = (x: number, y: number, terminalId: string) => {
      if (!terminalId) return
      setState({ x, y, terminalId })
    }
    const handler = (event: Event) => {
      const detail = (
        event as CustomEvent<{ x: number; y: number; terminalId?: string }>
      ).detail
      if (!detail) return
      open(detail.x, detail.y, detail.terminalId ?? '')
    }
    const onSurfaceContextMenu = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      const host = target.closest('[data-terminal-portal-host]')
      if (!host) return
      event.preventDefault()
      event.stopPropagation()
      open(
        event.clientX,
        event.clientY,
        host.getAttribute('data-terminal-portal-host') ?? ''
      )
    }
    window.addEventListener(TERMINAL_SURFACE_MENU_EVENT, handler)
    window.addEventListener('contextmenu', onSurfaceContextMenu, true)
    return () => {
      window.removeEventListener(TERMINAL_SURFACE_MENU_EVENT, handler)
      window.removeEventListener('contextmenu', onSurfaceContextMenu, true)
    }
  }, [])

  if (!state) return null

  const split = (
    direction: PaneSplitDirection,
    side: 'before' | 'after'
  ) => {
    const terminalId = state.terminalId
    close()
    onSplitPane(terminalId, direction, side)
  }

  return (
    <TabContextMenuShell x={state.x} y={state.y} onClose={close}>
      <TabContextItem
        icon={<ClipboardPaste />}
        label="Paste"
        onClick={() => {
          requestTerminalPaste(state.terminalId)
          close()
        }}
      />
      <TabContextSeparator />
      <TerminalThemeSubmenu onDone={close} />
      <TabContextSeparator />
      <TabContextItem
        icon={<SplitRightIcon />}
        label="Split pane right"
        onClick={() => split('horizontal', 'after')}
      />
      <TabContextItem
        icon={<SplitLeftIcon />}
        label="Split pane left"
        onClick={() => split('horizontal', 'before')}
      />
      <TabContextItem
        icon={<SplitDownIcon />}
        label="Split pane down"
        onClick={() => split('vertical', 'after')}
      />
      <TabContextItem
        icon={<SplitUpIcon />}
        label="Split pane up"
        onClick={() => split('vertical', 'before')}
      />
    </TabContextMenuShell>
  )
}
