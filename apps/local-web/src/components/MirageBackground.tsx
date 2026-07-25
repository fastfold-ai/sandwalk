import './MirageBackground.css'

import { useId, useMemo } from 'react'

import {
  MIRAGE_CIRCLE_COUNT,
  MIRAGE_CX,
  MIRAGE_FIRST_CY,
  MIRAGE_RADIUS,
  MIRAGE_SPACING,
  MIRAGE_VIEWBOX_HEIGHT,
  MIRAGE_VIEWBOX_WIDTH
} from '@/components/mirageGeometry'

import {
  buildMirageForm,
  type CircleDefinition,
  normalizeMirageId} from './mirage-background-form'
import {
  MirageBackgroundDefs,
  MirageBackgroundPattern
} from './mirage-background-svg'

type MirageBackgroundProps = {
  className?: string
}

export function MirageBackground({ className = '' }: MirageBackgroundProps) {
  const rawId = useId()
  const id = normalizeMirageId(rawId)

  const circles = useMemo<CircleDefinition[]>(
    () =>
      Array.from({ length: MIRAGE_CIRCLE_COUNT }, (_, index) => ({
        cx: MIRAGE_CX,
        cy: MIRAGE_FIRST_CY + index * MIRAGE_SPACING,
        radius: MIRAGE_RADIUS
      })),
    []
  )

  const form = useMemo(() => buildMirageForm(circles), [circles])

  return (
    <div className={`mirage-background ${className}`.trim()} aria-hidden="true">
      <svg
        className="mirage-background__svg"
        viewBox={`0 0 ${MIRAGE_VIEWBOX_WIDTH} ${MIRAGE_VIEWBOX_HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        role="presentation"
      >
        <MirageBackgroundDefs id={id} circles={circles} />
        <MirageBackgroundPattern id={id} form={form} circles={circles} />

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
