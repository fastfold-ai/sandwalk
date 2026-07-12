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
const CIRCLE_COUNT = 4
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

/** Path centerline x-offset — a calm vertical meander like the poster. */
function pathX(
  y: number,
  y0: number,
  height: number,
  cx: number,
  phase = 0
): number {
  const t = (y - y0) / Math.max(height, 1)
  return (
    cx +
    Math.sin(t * Math.PI * 2.6 + phase) * 30 +
    Math.sin(t * Math.PI * 4.9 + phase * 1.3) * 13 +
    Math.sin(t * Math.PI * 8.3 + phase * 0.7) * 6 +
    Math.cos(t * Math.PI * 1.4 + phase) * 10
  )
}

/** Ribbon half-thickness — widest through the middle, quiet at the bottom. */
function pathHalfWidth(t: number): number {
  const body = 30 + Math.sin(t * Math.PI * 2.8) * 9
  const taper = t > 0.74 ? 1 - ((t - 0.74) / 0.26) * 0.75 : 1
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
      // Sand matrices — light + dark patches flanking the path (like the ref).
      duneSoft: buildRibbonPath(y0, y1, CX - 30, 48, 2.4, 2.2),
      charcoalRight: buildRibbonPath(y0, y1, CX + 104, 48, 4.9, 1.25),
      charcoalLeft: buildRibbonPath(y0, y1, CX - 112, 48, 1.7, 1.1),
      olive: buildRibbonPath(y0, y1, CX + 66, 44, 3.5, 0.95),
      // The gold path — dark rim, gradient body, hot core, ink edges.
      goldRim: buildRibbonPath(y0, y1, CX, 84, 0, 1.18),
      gold: buildRibbonPath(y0, y1, CX, 84, 0, 1),
      goldCore: buildRibbonPath(y0, y1, CX, 72, 0.07, 0.44),
      edgeLeft: buildEdgeStroke(y0, y1, CX, 72, 0, -1),
      edgeRight: buildEdgeStroke(y0, y1, CX, 72, 0, 1),
      streak: buildEdgeStroke(y0, y1, CX, 72, 0.18, -0.35)
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
        </defs>

        <g className="mirage-background__fills">
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
                <path
                  className="mirage-pattern__dune"
                  d={form.duneSoft}
                />
                <path
                  className="mirage-pattern__patch mirage-pattern__patch--olive"
                  d={form.olive}
                />
                <path
                  className="mirage-pattern__patch mirage-pattern__patch--charcoal"
                  d={form.charcoalLeft}
                />
                <path
                  className="mirage-pattern__patch mirage-pattern__patch--charcoal"
                  d={form.charcoalRight}
                />

                <path className="mirage-pattern__gold-rim" d={form.goldRim} />
                <path
                  className="mirage-pattern__gold"
                  d={form.gold}
                  fill={`url(#${id}-gold)`}
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
