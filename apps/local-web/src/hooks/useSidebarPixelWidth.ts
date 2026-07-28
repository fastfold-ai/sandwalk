import type { RefObject } from 'react'
import { useEffect, useRef } from 'react'
import {
  getPanelGroupElement,
  type ImperativePanelHandle
} from 'react-resizable-panels'

export const SIDEBAR_MIN_WIDTH_PX = 243
export const SHELL_PANEL_GROUP_ID = 'shell-panels'

/** Keep sidebar at a fixed pixel width when the window/group resizes. */
export function useSidebarPixelWidth(
  sidebarPanelRef: RefObject<ImperativePanelHandle | null>,
  sidebarCollapsed: boolean
) {
  const pixelWidthRef = useRef(0)

  const rememberFromPercent = (sizePercent: number) => {
    if (sizePercent <= 0) return
    const group = getPanelGroupElement(SHELL_PANEL_GROUP_ID)
    if (!group) return
    const width = group.clientWidth
    if (width <= 0) return
    pixelWidthRef.current = (sizePercent / 100) * width
  }

  const applyPixelWidth = () => {
    const panel = sidebarPanelRef.current
    const px = pixelWidthRef.current
    if (!panel || px <= 0 || panel.isCollapsed()) return
    const group = getPanelGroupElement(SHELL_PANEL_GROUP_ID)
    if (!group) return
    const width = group.clientWidth
    if (width <= 0) return
    const next = (px / width) * 100
    if (Math.abs(panel.getSize() - next) < 0.05) return
    panel.resize(next)
  }

  useEffect(() => {
    const group = getPanelGroupElement(SHELL_PANEL_GROUP_ID)
    if (!group) return

    const panel = sidebarPanelRef.current
    if (panel && !panel.isCollapsed() && pixelWidthRef.current <= 0) {
      rememberFromPercent(panel.getSize())
    }

    const observer = new ResizeObserver(() => {
      applyPixelWidth()
    })
    observer.observe(group)
    return () => observer.disconnect()
  }, [sidebarPanelRef])

  useEffect(() => {
    if (sidebarCollapsed) return
    // Library restore is %-based; re-apply stored pixels after expand.
    applyPixelWidth()
  }, [sidebarCollapsed, sidebarPanelRef])

  return { onSidebarResize: rememberFromPercent }
}
