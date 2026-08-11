/**
 * Content floor for session chrome tabs — must match the pnpm patch on
 * `@sinm/react-chrome-tabs` (`TAB_CONTENT_MIN_WIDTH = 96`).
 * Outer ≈ content + 2× side margin (min outer ≈ 120, max outer ≈ 264).
 */
export const CHROME_TAB_CONTENT_MIN_WIDTH = 96
export const CHROME_TAB_SIDE_MARGIN = 12
export const CHROME_TAB_OVERLAP_DISTANCE = 1

/**
 * Tab silhouette (viewBox 214×36). Rendered inline per tab via <svg><path/>.
 *
 * Top corners 10 · bottom ears curve from the floor straight to the body
 * (no vertical stub). Ears sized 10×11 for a slim, one-piece silhouette.
 */
export const CHROME_TAB_GEOMETRY_PATH =
  'M20 0h174v36H0c5 0 10-4 10-11V10c0-5.5 4.5-10 10-10z'

export const chromeTabMinOuter =
  CHROME_TAB_CONTENT_MIN_WIDTH + 2 * CHROME_TAB_SIDE_MARGIN

export const chromeTabOverlap =
  2 * CHROME_TAB_SIDE_MARGIN + CHROME_TAB_OVERLAP_DISTANCE
