import type { RefObject } from 'react'
import { useEffect, useLayoutEffect } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'

import {
  FILES_PANEL_COLLAPSED_STORAGE_KEY,
  SIDEBAR_COLLAPSED_STORAGE_KEY,
  TERMINAL_OPEN_STORAGE_KEY,
  writeCollapsedSidebarSections
} from '@/lib/app-storage'

type PanelPersistenceArgs = {
  sidebarCollapsed: boolean
  filesPanelCollapsed: boolean
  terminalOpen: boolean
  sidebarPanelRef: RefObject<ImperativePanelHandle | null>
  filesPanelRef: RefObject<ImperativePanelHandle | null>
  collapsedSidebarSections: Record<string, boolean>
  sessionId: string | null
}

export function useAppPanelPersistence({
  sidebarCollapsed,
  filesPanelCollapsed,
  terminalOpen,
  sidebarPanelRef,
  filesPanelRef,
  collapsedSidebarSections,
  sessionId
}: PanelPersistenceArgs) {
  useEffect(() => {
    try {
      localStorage.setItem(
        SIDEBAR_COLLAPSED_STORAGE_KEY,
        sidebarCollapsed ? '1' : '0'
      )
    } catch {
      // ignore storage failures
    }
  }, [sidebarCollapsed])

  useEffect(() => {
    try {
      localStorage.setItem(
        FILES_PANEL_COLLAPSED_STORAGE_KEY,
        filesPanelCollapsed ? '1' : '0'
      )
    } catch {
      // ignore storage failures
    }
  }, [filesPanelCollapsed])

  useEffect(() => {
    try {
      localStorage.setItem(TERMINAL_OPEN_STORAGE_KEY, terminalOpen ? '1' : '0')
    } catch {
      // ignore storage failures
    }
  }, [terminalOpen])

  useEffect(() => {
    const panel = sidebarPanelRef.current
    if (!panel) return
    if (sidebarCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [sidebarCollapsed, sidebarPanelRef])

  // Layout phase so autoSave restore cannot flash the Files panel open on
  // New Agent before React state (collapsed) wins.
  useLayoutEffect(() => {
    const panel = filesPanelRef.current
    if (!panel) return
    if (filesPanelCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [filesPanelCollapsed, sessionId, filesPanelRef])

  useEffect(() => {
    writeCollapsedSidebarSections(collapsedSidebarSections)
  }, [collapsedSidebarSections])
}
