/** Shared Mirage plate geometry — gold thinking-path and sand matrices. */

export const MIRAGE_RADIUS = 160
export const MIRAGE_PAD = 44
export const MIRAGE_CX = MIRAGE_RADIUS + MIRAGE_PAD
export const MIRAGE_FIRST_CY = MIRAGE_RADIUS + MIRAGE_PAD
export const MIRAGE_CIRCLE_COUNT = 3
export const MIRAGE_SPACING = MIRAGE_RADIUS
export const MIRAGE_VIEWBOX_WIDTH = MIRAGE_RADIUS * 2 + MIRAGE_PAD * 2
export const MIRAGE_VIEWBOX_HEIGHT =
  MIRAGE_FIRST_CY + MIRAGE_SPACING * (MIRAGE_CIRCLE_COUNT - 1) + MIRAGE_RADIUS + MIRAGE_PAD

/** Skewed sine — sharpens wave crests into the poster's zig-zag turns. */
export function mirageZig(t: number, freq: number, phase: number): number {
  const angle = t * Math.PI * freq + phase
  return Math.sin(angle + 0.9 * Math.sin(angle * 2))
}

/**
 * Path centerline x-offset — big meander with sharp switchbacks like the
 * ref plate; amplitude swells through the middle and relaxes at the ends.
 */
export function miragePathX(
  y: number,
  y0: number,
  height: number,
  cx: number,
  phase = 0
): number {
  const t = (y - y0) / Math.max(height, 1)
  const swell = 0.72 + 0.42 * Math.sin(t * Math.PI * 1.2 + 0.3)
  return (
    cx +
    Math.sin(t * Math.PI * 1.1 + 0.3 + phase) * 30 +
    mirageZig(t, 3.1, phase) * 30 * swell +
    mirageZig(t, 6.3, phase * 1.5 + 1.2) * 11 * swell +
    Math.cos(t * Math.PI * 0.7 + phase) * 12
  )
}

/** Ribbon half-thickness — full at the bottom, thinning toward the top. */
export function miragePathHalfWidth(t: number): number {
  const body = 28 + Math.sin(t * Math.PI * 2.2 + 0.6) * 9
  const taper = t < 0.26 ? 1 - ((0.26 - t) / 0.26) * 0.6 : 1
  return Math.max(8, body * taper)
}

export function mirageBuildRibbonPath(
  y0: number,
  y1: number,
  cx: number,
  samples = 72,
  phase = 0,
  widthScale = 1
): string {
  const height = y1 - y0
  const left: string[] = []
  const right: string[] = []

  for (let i = 0; i <= samples; i += 1) {
    const t = i / samples
    const y = y0 + height * t
    const x = miragePathX(y, y0, height, cx, phase)
    const half = miragePathHalfWidth(t) * widthScale
    left.push(`${i === 0 ? 'M' : 'L'} ${(x - half).toFixed(2)} ${y.toFixed(2)}`)
    right.push(`L ${(x + half).toFixed(2)} ${y.toFixed(2)}`)
  }

  return `${left.join(' ')} ${right.reverse().join(' ')} Z`
}

/**
 * Localized organic blob — a wavy patch that fades in and out (gaussian
 * envelope) so bare sand shows between patches, like the poster matrices.
 */
export function mirageBuildBlobPath(
  y0: number,
  y1: number,
  bx: number,
  centerT: number,
  spreadT: number,
  maxHalf: number,
  phase = 0,
  samples = 48
): string {
  const height = y1 - y0
  const tStart = Math.max(0, centerT - spreadT * 1.9)
  const tEnd = Math.min(1, centerT + spreadT * 1.9)
  const left: string[] = []
  const right: string[] = []

  for (let i = 0; i <= samples; i += 1) {
    const t = tStart + ((tEnd - tStart) * i) / samples
    const y = y0 + height * t
    const env = Math.exp(-(((t - centerT) / spreadT) ** 2))
    const half = maxHalf * env
    const x =
      bx +
      Math.sin(t * Math.PI * 3.1 + phase) * 16 +
      Math.sin(t * Math.PI * 6.4 + phase * 1.7) * 7
    left.push(`${i === 0 ? 'M' : 'L'} ${(x - half).toFixed(2)} ${y.toFixed(2)}`)
    right.push(`L ${(x + half).toFixed(2)} ${y.toFixed(2)}`)
  }

  return `${left.join(' ')} ${right.reverse().join(' ')} Z`
}

export function mirageBuildEdgeStroke(
  y0: number,
  y1: number,
  cx: number,
  samples = 64,
  phase = 0,
  offset = -1
): string {
  const height = y1 - y0
  const parts: string[] = []
  for (let i = 0; i <= samples; i += 1) {
    const t = i / samples
    const y = y0 + height * t
    const x = miragePathX(y, y0, height, cx, phase)
    const half = miragePathHalfWidth(t) * offset
    parts.push(
      `${i === 0 ? 'M' : 'L'} ${(x + half).toFixed(2)} ${y.toFixed(2)}`
    )
  }
  return parts.join(' ')
}

export function mirageCapsulePath(
  firstCy: number,
  lastCy: number,
  cx: number,
  r: number
): string {
  return [
    `M ${cx - r} ${firstCy}`,
    `A ${r} ${r} 0 0 1 ${cx + r} ${firstCy}`,
    `L ${cx + r} ${lastCy}`,
    `A ${r} ${r} 0 0 1 ${cx - r} ${lastCy}`,
    'Z'
  ].join(' ')
}

/** Approximate polyline length for stroke-dash animations. */
export function miragePolylineLength(d: string): number {
  const nums = d.match(/-?\d+(?:\.\d+)?/g)?.map(Number) ?? []
  if (nums.length < 4) return 400
  let length = 0
  let prevX = nums[0]!
  let prevY = nums[1]!
  for (let i = 2; i + 1 < nums.length; i += 2) {
    const x = nums[i]!
    const y = nums[i + 1]!
    length += Math.hypot(x - prevX, y - prevY)
    prevX = x
    prevY = y
  }
  return Math.max(length, 1)
}
