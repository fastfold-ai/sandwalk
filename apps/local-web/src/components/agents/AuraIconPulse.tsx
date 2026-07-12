import { useEffect, useState } from 'react'

const AURA_MONO_PATHS = [
  'M13 149l0 0c-7,0 -14,6 -14,13l0 27c0,7 6,14 14,14l0 0c7,0 13,-6 13,-14l0 -27c0,-7 -6,-13 -13,-13z',
  'M54 81l0 0c-7,0 -14,6 -14,14l0 68c0,7 6,13 14,13l0 0c7,0 13,-6 13,-13l0 -68c0,-7 -6,-14 -13,-14z',
  'M95 41l0 0c-7,0 -14,6 -14,14l0 95c0,7 6,13 14,13l0 0c7,0 14,-6 14,-13l0 -95c0,-7 -6,-14 -14,-14z',
  'M135 75l0 0c-7,0 -14,6 -14,14l0 95c0,7 6,14 14,14l0 0c7,0 13,-6 13,-14l0 -95c0,-7 -6,-14 -13,-14z',
  'M176 108l0 0c-7,0 -14,6 -14,13l0 95c0,7 6,14 14,14l0 0c7,0 14,-6 14,-14l0 -95c0,-7 -6,-13 -14,-13z',
  'M217 95l0 0c-7,0 -13,6 -13,14l0 69c0,7 6,13 13,13l0 0c7,0 14,-6 14,-13l0 -69c0,-7 -6,-14 -14,-14z',
  'M257 68l0 0c-7,0 -13,6 -13,14l0 27c0,7 6,13 13,13l0 0c7,0 14,-6 14,-13l0 -27c0,-7 -6,-14 -14,-14z'
] as const

const AURA_COLOR_BARS = [
  {
    color: '#DB0096',
    d: 'M13 149l0 0c-7,0 -14,6 -14,13l0 27c0,7 6,14 14,14l0 0c7,0 13,-6 13,-14l0 -27c0,-7 -6,-13 -13,-13z'
  },
  {
    color: '#E56464',
    d: 'M54 81l0 0c-7,0 -14,6 -14,14l0 68c0,7 6,13 14,13l0 0c7,0 13,-6 13,-13l0 -68c0,-7 -6,-14 -13,-14z'
  },
  {
    color: '#FFB12F',
    d: 'M95 41l0 0c-7,0 -14,6 -14,14l0 95c0,7 6,13 14,13l0 0c7,0 14,-6 14,-13l0 -95c0,-7 -6,-14 -14,-14z'
  },
  {
    color: '#89CC67',
    d: 'M135 75l0 0c-7,0 -14,6 -14,14l0 95c0,7 6,14 14,14l0 0c7,0 13,-6 13,-14l0 -95c0,-7 -6,-14 -13,-14z'
  },
  {
    color: '#13D8A3',
    d: 'M176 108l0 0c-7,0 -14,6 -14,13l0 95c0,7 6,14 14,14l0 0c7,0 14,-6 14,-14l0 -95c0,-7 -6,-13 -14,-13z'
  },
  {
    color: '#15A3D0',
    d: 'M217 95l0 0c-7,0 -13,6 -13,14l0 69c0,7 6,13 13,13l0 0c7,0 14,-6 14,-13l0 -69c0,-7 -6,-14 -14,-14z'
  },
  {
    color: '#1678F1',
    d: 'M257 68l0 0c-7,0 -13,6 -13,14l0 27c0,7 6,13 13,13l0 0c7,0 14,-6 14,-13l0 -27c0,-7 -6,-14 -14,-14z'
  }
] as const

export function AuraIconPulse({
  className,
  animateTick = 0
}: {
  className?: string
  animateTick?: number
}) {
  const [hovered, setHovered] = useState(false)
  const [sendingPulse, setSendingPulse] = useState(false)

  useEffect(() => {
    if (animateTick <= 0) return
    setSendingPulse(true)
    const timer = window.setTimeout(() => setSendingPulse(false), 700)
    return () => window.clearTimeout(timer)
  }, [animateTick])

  const showColor = hovered || sendingPulse

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 271 271"
      aria-label="Aura"
      role="img"
      className={className}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <g>
        {AURA_MONO_PATHS.map((d, index) => (
          <path key={`mono-${index}`} d={d} fill="currentColor" />
        ))}
      </g>
      <g>
        {AURA_COLOR_BARS.map((bar, index) => (
          <path
            key={`color-${index}`}
            d={bar.d}
            fill={bar.color}
            style={{
              opacity: showColor ? 1 : 0,
              transitionProperty: 'opacity',
              transitionDuration: '170ms',
              transitionTimingFunction: 'ease-out',
              transitionDelay: showColor ? `${index * 55}ms` : '0ms'
            }}
          />
        ))}
      </g>
    </svg>
  )
}
