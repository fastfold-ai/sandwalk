import './MirageWalkPath.css'

import { useId, useMemo } from 'react'

import {
  mirageBuildRibbonPath,
  miragePathX,
  MIRAGE_RADIUS
} from '@/components/mirageGeometry'
import { ONBOARDING_STEPS } from '@/lib/onboarding'
import { cn } from '@/lib/utils'

type MirageWalkPathProps = {
  className?: string
  /** Center hero on welcome, or compact rail beside content. */
  variant?: 'hero' | 'rail'
  step?: number
  onStepChange?: (step: number) => void
  /** Play the path reveal animation (welcome). */
  animateAppear?: boolean
}

function normalizeId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '')
}

/**
 * Gold walking path from the login Mirage plate, with step dots matching
 * the top onboarding progress circles.
 */
export function MirageWalkPath({
  className,
  variant = 'hero',
  step = 0,
  onStepChange,
  animateAppear = false
}: MirageWalkPathProps) {
  const rawId = useId()
  const id = normalizeId(rawId)
  const isRail = variant === 'rail'
  const interactive = typeof onStepChange === 'function'

  const width = isRail ? 140 : MIRAGE_RADIUS * 2 + 24
  const height = isRail ? 340 : MIRAGE_RADIUS * 2 + 48
  const cx = width / 2
  // Tight top so the gold starts under the copy with little empty SVG pad.
  const padY = isRail ? 20 : 8
  const y0 = padY
  const y1 = height - (isRail ? 20 : 16)
  const ribbonScale = isRail ? 0.72 : 1.05

  const form = useMemo(() => {
    const span = y1 - y0
    const stops = ONBOARDING_STEPS.map((item, index) => {
      const t =
        ONBOARDING_STEPS.length <= 1
          ? 0
          : index / (ONBOARDING_STEPS.length - 1)
      const y = y0 + span * t
      const x = miragePathX(y, y0, span, cx)
      return { ...item, index, x, y, t }
    })
    return {
      goldRim: mirageBuildRibbonPath(y0, y1, cx, 96, 0, 1.18 * ribbonScale),
      gold: mirageBuildRibbonPath(y0, y1, cx, 96, 0, 1 * ribbonScale),
      strandOrange: mirageBuildRibbonPath(
        y0,
        y1,
        cx + 4,
        88,
        0.34,
        0.34 * ribbonScale
      ),
      strandPale: mirageBuildRibbonPath(
        y0,
        y1,
        cx - 5,
        88,
        -0.3,
        0.3 * ribbonScale
      ),
      goldCore: mirageBuildRibbonPath(
        y0,
        y1,
        cx,
        88,
        0.07,
        0.4 * ribbonScale
      ),
      stops
    }
  }, [cx, ribbonScale, y0, y1])

  return (
    <div
      className={cn(
        'mirage-walk',
        isRail ? 'mirage-walk--rail' : 'mirage-walk--hero',
        animateAppear && 'mirage-walk--appear',
        className
      )}
    >
      <div className="mirage-walk__frame">
        <svg
          className="mirage-walk__svg"
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          role="presentation"
          aria-hidden="true"
        >
          <defs>
            <filter
              id={`${id}-marble`}
              x="-20%"
              y="-10%"
              width="140%"
              height="120%"
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
                scale={isRail ? 10 : 14}
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

            <clipPath id={`${id}-reveal`}>
              <rect
                className="mirage-walk__reveal-rect"
                x={0}
                y={0}
                width={width}
                height={height}
              />
            </clipPath>
          </defs>

          <g
            className="mirage-walk__path-layer"
            clipPath={animateAppear ? `url(#${id}-reveal)` : undefined}
          >
            <g className="mirage-walk__fills" filter={`url(#${id}-marble)`}>
              <path className="mirage-walk__gold-rim" d={form.goldRim} />
              <path
                className="mirage-walk__gold"
                d={form.gold}
                fill={`url(#${id}-gold)`}
              />
              <path
                className="mirage-walk__strand-orange"
                d={form.strandOrange}
              />
              <path className="mirage-walk__strand-pale" d={form.strandPale} />
              <path className="mirage-walk__gold-core" d={form.goldCore} />
            </g>
          </g>
        </svg>

        {interactive ? (
          <nav className="mirage-walk__dots" aria-label="Setup steps">
            {form.stops.map(stop => {
              const active = stop.index === step
              const done = stop.index < step
              return (
                <button
                  key={stop.id}
                  type="button"
                  title={stop.title}
                  className={cn(
                    'mirage-walk__dot',
                    active && 'mirage-walk__dot--active',
                    done && !active && 'mirage-walk__dot--done',
                    animateAppear && 'mirage-walk__dot--enter'
                  )}
                  style={{
                    left: `${(stop.x / width) * 100}%`,
                    top: `${(stop.y / height) * 100}%`,
                    ...(animateAppear
                      ? { animationDelay: `${700 + stop.index * 120}ms` }
                      : {})
                  }}
                  onClick={() => onStepChange(stop.index)}
                  aria-label={stop.title}
                  aria-current={active ? 'step' : undefined}
                />
              )
            })}
          </nav>
        ) : null}
      </div>
    </div>
  )
}
