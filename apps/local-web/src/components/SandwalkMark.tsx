import { cn } from '@/lib/utils'

/** Aura mark paths (same as public/aura_icon.svg). */
const AURA_PATHS = [
  'M739 248c-19 0-35 16-35 35v70c0 19 16 35 35 35s35-16 35-35v-70c0-19-16-35-35-35z',
  'M318 177c-19 0-35 16-35 35v246c0 19 16 35 35 35s35-16 35-35V212c0-19-16-35-35-35z',
  'M213 283c-19 0-35 16-35 35v176c0 19 16 35 35 35s35-16 35-35V318c0-19-16-35-35-35z',
  'M107 458c-19 0-35 16-35 35v70c0 19 16 35 35 35s35-16 35-35v-70c0-19-16-35-35-35z',
  'M422 265c-19 0-35 16-35 35v246c0 19 16 35 35 35s35-16 35-35V300c0-19-16-35-35-35z',
  'M634 318c-19 0-35 16-35 35v178c0 19 16 35 35 35s35-16 35-35V353c0-19-16-35-35-35z',
  'M529 353c-19 0-35 16-35 35v246c0 19 16 35 35 35s35-16 35-35V388c0-19-16-35-35-35z'
] as const

/**
 * Sandwalk mark — Aura bars (inherits text color).
 */
export function SandwalkMark({
  className,
  title = 'sandwalk'
}: {
  className?: string
  title?: string
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 847 847"
      role="img"
      aria-label={title}
      className={cn('h-full w-auto shrink-0', className)}
    >
      <g fill="currentColor">
        {AURA_PATHS.map((d, i) => (
          <path key={i} d={d} />
        ))}
      </g>
    </svg>
  )
}
