/**
 * Content floor for session chrome tabs — must match the pnpm patch on
 * `@sinm/react-chrome-tabs` (`TAB_CONTENT_MIN_WIDTH = 200`).
 * Outer ≈ content + 2× side margin. Used only for +N capacity math.
 */
export const CHROME_TAB_CONTENT_MIN_WIDTH = 200
export const CHROME_TAB_SIDE_MARGIN = 12
export const CHROME_TAB_OVERLAP_DISTANCE = 1

/**
 * Active-tab SVG silhouette (viewBox 214×36). Must match the patched
 * `tabTemplate` path in `@sinm/react-chrome-tabs`. Forced onto DOM paths
 * because duplicate symbol ids make `<use>` stick to the first (stale) path.
 *
 * Top corners 12 · bottom ears 12×11 · stub 3.
 */
export const CHROME_TAB_GEOMETRY_PATH =
  'M24 0h190v36H0v-3c6 0 12-5 12-11V12c0-6.75 5.25-12 12-12z'

export const chromeTabMinOuter =
  CHROME_TAB_CONTENT_MIN_WIDTH + 2 * CHROME_TAB_SIDE_MARGIN

export const chromeTabOverlap =
  2 * CHROME_TAB_SIDE_MARGIN + CHROME_TAB_OVERLAP_DISTANCE
