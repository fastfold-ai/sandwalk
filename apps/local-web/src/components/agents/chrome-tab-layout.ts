/**
 * Content floor for session chrome tabs — must match the pnpm patch on
 * `@sinm/react-chrome-tabs` (`TAB_CONTENT_MIN_WIDTH = 200`).
 * Outer ≈ content + 2× side margin. Used only for +N capacity math.
 */
export const CHROME_TAB_CONTENT_MIN_WIDTH = 200
export const CHROME_TAB_SIDE_MARGIN = 9
export const CHROME_TAB_OVERLAP_DISTANCE = 1

export const chromeTabMinOuter =
  CHROME_TAB_CONTENT_MIN_WIDTH + 2 * CHROME_TAB_SIDE_MARGIN

export const chromeTabOverlap =
  2 * CHROME_TAB_SIDE_MARGIN + CHROME_TAB_OVERLAP_DISTANCE
