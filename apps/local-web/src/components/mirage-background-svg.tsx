import {
  MIRAGE_VIEWBOX_HEIGHT,
  MIRAGE_VIEWBOX_WIDTH
} from '@/components/mirageGeometry'

import type { buildMirageForm, CircleDefinition } from './mirage-background-form'

export function MirageBackgroundDefs({
  id,
  circles
}: {
  id: string
  circles: CircleDefinition[]
}) {
  return (
    <defs>
      <filter id={`${id}-grain`} x="-10%" y="-10%" width="120%" height="120%">
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

      <filter id={`${id}-marble`} x="-15%" y="-15%" width="130%" height="130%">
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

      <linearGradient id={`${id}-gold`} x1="0%" y1="0%" x2="100%" y2="100%">
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
  )
}

export function MirageBackgroundPattern({
  id,
  form,
  circles
}: {
  id: string
  form: ReturnType<typeof buildMirageForm>
  circles: CircleDefinition[]
}) {
  return (
    <g className="mirage-background__fills" mask={`url(#${id}-holes)`}>
      <g clipPath={`url(#${id}-stack)`}>
        <g className="mirage-pattern">
          <rect
            className="mirage-pattern__sand"
            x={form.left}
            y={form.top}
            width={circles[0]!.radius * 2}
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
            <path className="mirage-pattern__ink" d={form.edgeLeft} fill="none" />
            <path className="mirage-pattern__ink" d={form.edgeRight} fill="none" />
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
  )
}
