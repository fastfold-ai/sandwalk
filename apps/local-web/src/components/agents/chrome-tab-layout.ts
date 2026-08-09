/** Content floor for session chrome tabs (outer ≈ content + 2×margin). */
export const CHROME_TAB_CONTENT_MIN_WIDTH = 200
export const CHROME_TAB_SIDE_MARGIN = 9
export const CHROME_TAB_CONTENT_MAX_WIDTH = 240
export const CHROME_TAB_OVERLAP_DISTANCE = 1

export const chromeTabMinOuter =
  CHROME_TAB_CONTENT_MIN_WIDTH + 2 * CHROME_TAB_SIDE_MARGIN

/**
 * Vite can serve a stale prebundle of @sinm/react-chrome-tabs with min=60.
 * Re-apply our floor on the live DOM after each lib layout pass.
 */
export function enforceChromeTabMinWidths(
  strip: HTMLElement,
  extraGapPx: number
) {
  const tabs = [...strip.querySelectorAll('.chrome-tab')] as HTMLElement[]
  if (tabs.length === 0) return

  const tooSmall = tabs.some(tab => {
    const width = parseFloat(tab.style.width || '0')
    return width > 0 && width + 0.5 < chromeTabMinOuter
  })
  if (!tooSmall) return

  const toolbar = strip.querySelector('.chrome-tabs-toolbar-right')
  const toolbarWidth = toolbar instanceof HTMLElement ? toolbar.clientWidth : 0
  const tabsContentWidth = strip.clientWidth - toolbarWidth - 16
  const count = tabs.length
  const overlapped = (count - 1) * CHROME_TAB_OVERLAP_DISTANCE
  const target =
    (tabsContentWidth - 2 * CHROME_TAB_SIDE_MARGIN + overlapped) / count
  const contentWidth = Math.max(
    CHROME_TAB_CONTENT_MIN_WIDTH,
    Math.min(CHROME_TAB_CONTENT_MAX_WIDTH, Math.floor(target))
  )
  const outer = contentWidth + 2 * CHROME_TAB_SIDE_MARGIN

  let contentPos = CHROME_TAB_SIDE_MARGIN
  tabs.forEach((tab, i) => {
    const widthPx = `${outer}px`
    if (tab.style.width !== widthPx) tab.style.width = widthPx
    const tabPos =
      contentPos - i * CHROME_TAB_OVERLAP_DISTANCE - CHROME_TAB_SIDE_MARGIN
    contentPos += contentWidth
    const transform = `translate3d(${tabPos}px, 0, 0)`
    if (tab.style.transform !== transform) {
      tab.style.setProperty('transform', transform, 'important')
    }
    const gap = i === 0 ? '' : `${i * extraGapPx}px`
    if (tab.style.translate !== gap) tab.style.translate = gap
  })
}
