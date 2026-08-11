import {
  MIRAGE_CX,
  MIRAGE_RADIUS,
  mirageBuildBlobPath,
  mirageBuildEdgeStroke,
  mirageBuildRibbonPath,
  mirageCapsulePath} from '@/components/mirageGeometry'

export type CircleDefinition = {
  cx: number
  cy: number
  radius: number
}

export function normalizeMirageId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '')
}

export function buildMirageForm(circles: CircleDefinition[]) {
  const first = circles[0]!
  const last = circles[circles.length - 1]!
  const chords = circles.slice(0, -1).map((circle, index) => {
    const next = circles[index + 1]!
    return (circle.cy + next.cy) / 2
  })
  const top = first.cy - MIRAGE_RADIUS
  const bottom = last.cy + MIRAGE_RADIUS
  const y0 = top
  const y1 = bottom
  const cx = MIRAGE_CX

  return {
    capsule: mirageCapsulePath(first.cy, last.cy, cx, MIRAGE_RADIUS),
    chords,
    left: cx - MIRAGE_RADIUS,
    right: cx + MIRAGE_RADIUS,
    top,
    bottom,
    height: bottom - top,
    blobs: [
      {
        cls: 'olive',
        d: mirageBuildBlobPath(y0, y1, cx - 82, 0.1, 0.07, 52, 2.1)
      },
      {
        cls: 'charcoal',
        d: mirageBuildBlobPath(y0, y1, cx + 94, 0.15, 0.06, 46, 4.2)
      },
      {
        cls: 'dune',
        d: mirageBuildBlobPath(y0, y1, cx - 98, 0.31, 0.08, 54, 1.2)
      },
      {
        cls: 'charcoal',
        d: mirageBuildBlobPath(y0, y1, cx + 96, 0.5, 0.09, 64, 0.7)
      },
      {
        cls: 'olive',
        d: mirageBuildBlobPath(y0, y1, cx - 106, 0.61, 0.06, 40, 3.3)
      },
      {
        cls: 'dune',
        d: mirageBuildBlobPath(y0, y1, cx - 62, 0.73, 0.07, 56, 2.8)
      },
      {
        cls: 'charcoal',
        d: mirageBuildBlobPath(y0, y1, cx + 74, 0.84, 0.07, 48, 5.0)
      }
    ],
    goldRim: mirageBuildRibbonPath(y0, y1, cx, 96, 0, 1.18),
    gold: mirageBuildRibbonPath(y0, y1, cx, 96, 0, 1),
    strandOrange: mirageBuildRibbonPath(y0, y1, cx + 6, 88, 0.34, 0.34),
    strandPale: mirageBuildRibbonPath(y0, y1, cx - 8, 88, -0.3, 0.3),
    goldCore: mirageBuildRibbonPath(y0, y1, cx, 88, 0.07, 0.4),
    edgeLeft: mirageBuildEdgeStroke(y0, y1, cx, 88, 0, -1),
    edgeRight: mirageBuildEdgeStroke(y0, y1, cx, 88, 0, 1),
    streak: mirageBuildEdgeStroke(y0, y1, cx, 88, 0.18, -0.35),
    streakB: mirageBuildEdgeStroke(y0, y1, cx + 4, 88, 0.42, 0.28)
  }
}
