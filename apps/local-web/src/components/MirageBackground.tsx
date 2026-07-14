import './MirageBackground.css'

import { useId, useMemo } from 'react'

import {
  mirageBuildBlobPath,
  mirageBuildEdgeStroke,
  mirageBuildRibbonPath,
  mirageCapsulePath,
  MIRAGE_CIRCLE_COUNT,
  MIRAGE_CX,
  MIRAGE_FIRST_CY,
  MIRAGE_RADIUS,
  MIRAGE_SPACING,
  MIRAGE_VIEWBOX_HEIGHT,
  MIRAGE_VIEWBOX_WIDTH
} from '@/components/mirageGeometry'

type MirageBackgroundProps = {
  className?: string
}

type CircleDefinition = {
  cx: number
  cy: number
  radius: number
}

function normalizeId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '')
}

/**
 * Vertical Mirage stack, matching the poster plate:
 * overlapping circles, vertical capsule, horizontal chords,
 * gold thinking-path flowing down through the sand matrices.
 */
export function MirageBackground({ className = '' }: MirageBackgroundProps) {
  const rawId = useId()
  const id = normalizeId(rawId)

  const circles = useMemo<CircleDefinition[]>(
    () =>
      Array.from({ length: MIRAGE_CIRCLE_COUNT }, (_, index) => ({
        cx: MIRAGE_CX,
        cy: MIRAGE_FIRST_CY + index * MIRAGE_SPACING,
        radius: MIRAGE_RADIUS
      })),
    []
  )

  const form = useMemo(() => {
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
  }, [circles])

  return (
    <div className={`mirage-background ${className}`.trim()} aria-hidden="true">
      <svg
        className="mirage-background__svg"
        viewBox={`0 0 ${MIRAGE_VIEWBOX_WIDTH} ${MIRAGE_VIEWBOX_HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        role="presentation"
      >
        <defs>
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

          <mask id={`${id}-holes`}>
            <rect
              x="-20"
              y="-20"
              width={MIRAGE_VIEWBOX_WIDTH + 40}
              height={MIRAGE_VIEWBOX_HEIGHT + 40}
              fill="#000000"
            />
            <circle
              cx={circles[1]!.cx}
              cy={circles[1]!.cy}
              r={circles[1]!.radius}
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
                width={MIRAGE_RADIUS * 2}
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
                <path className="mirage-pattern__gold-core" d={form.goldCore} />
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

      <div className="mirage-background__overlay" />
    </div>
  )
}
