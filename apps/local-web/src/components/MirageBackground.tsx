import { useId, useMemo } from 'react'

import './MirageBackground.css'

type MirageBackgroundProps = {
  className?: string
}

type CircleDefinition = {
  cx: number
  cy: number
  radius: number
}

/**
 * Vertical Mirage stack, matching the poster plate:
 * 4 overlapping circles top→bottom, vertical capsule, horizontal chords,
 * gold thinking-path flowing down through the sand matrices.
 */
const RADIUS = 160
const PAD = 44
const CX = RADIUS + PAD
const FIRST_CY = RADIUS + PAD
const CIRCLE_COUNT = 3
const SPACING = RADIUS
const VIEWBOX_WIDTH = RADIUS * 2 + PAD * 2
const VIEWBOX_HEIGHT =
  FIRST_CY + SPACING * (CIRCLE_COUNT - 1) + RADIUS + PAD

function normalizeId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '')
}

function capsulePath(
  firstCy: number,
  lastCy: number,
  cx: number,
  r: number
): string {
  // Vertical stadium: top/bottom semicircles + left/right tangents.
  return [
    `M ${cx - r} ${firstCy}`,
    `A ${r} ${r} 0 0 1 ${cx + r} ${firstCy}`,
    `L ${cx + r} ${lastCy}`,
    `A ${r} ${r} 0 0 1 ${cx - r} ${lastCy}`,
    'Z'
  ].join(' ')
}

/** Skewed sine — sharpens wave crests into the poster's zig-zag turns. */
function zig(t: number, freq: number, phase: number): number {
  const angle = t * Math.PI * freq + phase
  return Math.sin(angle + 0.9 * Math.sin(angle * 2))
}

/**
 * Path centerline x-offset — big meander with sharp switchbacks like the
 * ref plate; amplitude swells through the middle and relaxes at the ends.
 */
function pathX(
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
    zig(t, 3.1, phase) * 30 * swell +
    zig(t, 6.3, phase * 1.5 + 1.2) * 11 * swell +
    Math.cos(t * Math.PI * 0.7 + phase) * 12
  )
}

/** Ribbon half-thickness — full at the bottom, thinning toward the top. */
function pathHalfWidth(t: number): number {
  const body = 28 + Math.sin(t * Math.PI * 2.2 + 0.6) * 9
  const taper = t < 0.26 ? 1 - ((0.26 - t) / 0.26) * 0.6 : 1
  return Math.max(8, body * taper)
}

function buildRibbonPath(
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
    const x = pathX(y, y0, height, cx, phase)
    const half = pathHalfWidth(t) * widthScale
    left.push(`${i === 0 ? 'M' : 'L'} ${(x - half).toFixed(2)} ${y.toFixed(2)}`)
    right.push(`L ${(x + half).toFixed(2)} ${y.toFixed(2)}`)
  }

  return `${left.join(' ')} ${right.reverse().join(' ')} Z`
}

/**
 * Localized organic blob — a wavy patch that fades in and out (gaussian
 * envelope) so bare sand shows between patches, like the poster matrices.
 */
function buildBlobPath(
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

function buildEdgeStroke(
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
    const x = pathX(y, y0, height, cx, phase)
    const half = pathHalfWidth(t) * offset
    parts.push(
      `${i === 0 ? 'M' : 'L'} ${(x + half).toFixed(2)} ${y.toFixed(2)}`
    )
  }
  return parts.join(' ')
}

export function MirageBackground({ className = '' }: MirageBackgroundProps) {
  const rawId = useId()
  const id = normalizeId(rawId)

  const circles = useMemo<CircleDefinition[]>(
    () =>
      Array.from({ length: CIRCLE_COUNT }, (_, index) => ({
        cx: CX,
        cy: FIRST_CY + index * SPACING,
        radius: RADIUS
      })),
    []
  )

  const form = useMemo(() => {
    const first = circles[0]
    const last = circles[circles.length - 1]
    const chords = circles.slice(0, -1).map((circle, index) => {
      const next = circles[index + 1]
      return (circle.cy + next.cy) / 2
    })
    const top = first.cy - RADIUS
    const bottom = last.cy + RADIUS
    const y0 = top
    const y1 = bottom

    return {
      capsule: capsulePath(first.cy, last.cy, CX, RADIUS),
      chords,
      left: CX - RADIUS,
      right: CX + RADIUS,
      top,
      bottom,
      height: bottom - top,
      // Localized matrices — blobs with bare sand between them (ref spacing).
      blobs: [
        { cls: 'olive', d: buildBlobPath(y0, y1, CX - 82, 0.1, 0.07, 52, 2.1) },
        {
          cls: 'charcoal',
          d: buildBlobPath(y0, y1, CX + 94, 0.15, 0.06, 46, 4.2)
        },
        {
          cls: 'dune',
          d: buildBlobPath(y0, y1, CX - 98, 0.31, 0.08, 54, 1.2)
        },
        {
          cls: 'charcoal',
          d: buildBlobPath(y0, y1, CX + 96, 0.5, 0.09, 64, 0.7)
        },
        {
          cls: 'olive',
          d: buildBlobPath(y0, y1, CX - 106, 0.61, 0.06, 40, 3.3)
        },
        {
          cls: 'dune',
          d: buildBlobPath(y0, y1, CX - 62, 0.73, 0.07, 56, 2.8)
        },
        {
          cls: 'charcoal',
          d: buildBlobPath(y0, y1, CX + 74, 0.84, 0.07, 48, 5.0)
        }
      ],
      // The gold path — dark rim, gradient body, braided strands, ink edges.
      goldRim: buildRibbonPath(y0, y1, CX, 96, 0, 1.18),
      gold: buildRibbonPath(y0, y1, CX, 96, 0, 1),
      strandOrange: buildRibbonPath(y0, y1, CX + 6, 88, 0.34, 0.34),
      strandPale: buildRibbonPath(y0, y1, CX - 8, 88, -0.3, 0.3),
      goldCore: buildRibbonPath(y0, y1, CX, 88, 0.07, 0.4),
      edgeLeft: buildEdgeStroke(y0, y1, CX, 88, 0, -1),
      edgeRight: buildEdgeStroke(y0, y1, CX, 88, 0, 1),
      streak: buildEdgeStroke(y0, y1, CX, 88, 0.18, -0.35),
      streakB: buildEdgeStroke(y0, y1, CX + 4, 88, 0.42, 0.28)
    }
  }, [circles])

  return (
    <div className={`mirage-background ${className}`.trim()} aria-hidden="true">
      <svg
        className="mirage-background__svg"
        viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        role="presentation"
      >
        <defs>
          {/* Print grain over the sand base. */}
          <filter
            id={`${id}-grain`}
            x="-10%"
            y="-10%"
            width="120%"
            height="120%"
          >
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.9"
              numOctaves="3"
              stitchTiles="stitch"
              result="noise"
            />
            <feColorMatrix
              in="noise"
              type="matrix"
              values="0 0 0 0 0.6
                      0 0 0 0 0.52
                      0 0 0 0 0.4
                      0 0 0 0.24 0"
              result="tint"
            />
            <feBlend in="SourceGraphic" in2="tint" mode="multiply" />
          </filter>

          {/* Liquid warp — the poster's marbled distortion, kept moderate. */}
          <filter
            id={`${id}-marble`}
            x="-15%"
            y="-15%"
            width="130%"
            height="130%"
          >
            <feTurbulence
              type="turbulence"
              baseFrequency="0.035 0.009"
              numOctaves="2"
              seed="7"
              result="warp"
            />
            <feDisplacementMap
              in="SourceGraphic"
              in2="warp"
              scale="20"
              xChannelSelector="R"
              yChannelSelector="G"
            />
          </filter>

          <linearGradient
            id={`${id}-gold`}
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop offset="0%" stopColor="#f2c14e" />
            <stop offset="45%" stopColor="#eda43a" />
            <stop offset="80%" stopColor="#e08a2d" />
            <stop offset="100%" stopColor="#d9962f" />
          </linearGradient>

          {/* Union of circles — one continuous clip, no seams. */}
          <clipPath id={`${id}-stack`}>
            {circles.map((circle, index) => (
              <circle
                key={`clip-${index}`}
                cx={circle.cx}
                cy={circle.cy}
                r={circle.radius}
              />
            ))}
          </clipPath>

          {/*
            The fill lives only inside the MIDDLE circle — its own outline
            is the cut, so the boundary is a real contour line (like the
            poster, where some circles are filled and others are empty).
            Wireframe is unaffected.
          */}
          <mask id={`${id}-holes`}>
            <rect
              x="-20"
              y="-20"
              width={VIEWBOX_WIDTH + 40}
              height={VIEWBOX_HEIGHT + 40}
              fill="#000000"
            />
            <circle
              cx={circles[1].cx}
              cy={circles[1].cy}
              r={circles[1].radius}
              fill="#ffffff"
            />
          </mask>
        </defs>

        <g className="mirage-background__fills" mask={`url(#${id}-holes)`}>
          <g clipPath={`url(#${id}-stack)`}>
            <g className="mirage-pattern">
              <rect
                className="mirage-pattern__sand"
                x={form.left}
                y={form.top}
                width={RADIUS * 2}
                height={form.height}
                filter={`url(#${id}-grain)`}
              />

              <g filter={`url(#${id}-marble)`}>
                {form.blobs.map((blob, index) => (
                  <path
                    key={`blob-${index}`}
                    className={`mirage-pattern__patch mirage-pattern__patch--${blob.cls}`}
                    d={blob.d}
                  />
                ))}

                <path className="mirage-pattern__gold-rim" d={form.goldRim} />
                <path
                  className="mirage-pattern__gold"
                  d={form.gold}
                  fill={`url(#${id}-gold)`}
                />
                <path
                  className="mirage-pattern__strand mirage-pattern__strand--orange"
                  d={form.strandOrange}
                />
                <path
                  className="mirage-pattern__strand mirage-pattern__strand--pale"
                  d={form.strandPale}
                />
                <path
                  className="mirage-pattern__gold-core"
                  d={form.goldCore}
                />
                <path
                  className="mirage-pattern__ink"
                  d={form.edgeLeft}
                  fill="none"
                />
                <path
                  className="mirage-pattern__ink"
                  d={form.edgeRight}
                  fill="none"
                />
                <path
                  className="mirage-pattern__ink mirage-pattern__ink--fine"
                  d={form.streak}
                  fill="none"
                />
                <path
                  className="mirage-pattern__ink mirage-pattern__ink--fine"
                  d={form.streakB}
                  fill="none"
                />
              </g>
            </g>
          </g>
        </g>

        <g className="mirage-form">
          <path className="mirage-form__capsule" d={form.capsule} />
          {circles.map((circle, index) => (
            <circle
              className="mirage-form__circle"
              key={`outline-${index}`}
              cx={circle.cx}
              cy={circle.cy}
              r={circle.radius}
            />
          ))}
          {form.chords.map((y, index) => (
            <line
              className="mirage-form__chord"
              key={`chord-${index}`}
              x1={form.left}
              y1={y}
              x2={form.right}
              y2={y}
            />
          ))}
        </g>
      </svg>

      {/* Soft vignette so the login card stays readable over the art. */}
      <div className="mirage-background__overlay" />
    </div>
  )
}
