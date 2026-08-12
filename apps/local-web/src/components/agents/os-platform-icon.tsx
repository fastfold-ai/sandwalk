import { cn } from '@/lib/utils'

export type OsPlatformKind = 'mac' | 'windows' | 'linux' | 'unknown'

/** Map `/v1/discover` platform strings to an OS family. */
export function osPlatformKind(platform: string | null | undefined): OsPlatformKind {
  const p = (platform || '').trim().toLowerCase()
  if (!p) return 'unknown'
  if (p === 'darwin' || p.includes('mac')) return 'mac'
  if (p.includes('win')) return 'windows'
  if (p.includes('linux')) return 'linux'
  return 'unknown'
}

const SRC: Record<Exclude<OsPlatformKind, 'unknown'>, string> = {
  mac: '/os/apple.svg',
  windows: '/os/windows.svg',
  linux: '/os/linux.svg'
}

/** Simple Icons (CC0) Apple / Windows / Linux marks. */
export function OsPlatformIcon({
  platform,
  className,
  dense = false
}: {
  platform: string | null | undefined
  className?: string
  /** Bare mark (no circle) for inline use next to hostnames. */
  dense?: boolean
}) {
  const kind = osPlatformKind(platform)
  if (kind === 'unknown') {
    if (dense) {
      return (
        <span
          className={cn(
            'text-muted-foreground inline-flex size-3.5 shrink-0 items-center justify-center text-[10px] font-medium',
            className
          )}
          aria-hidden
        >
          ?
        </span>
      )
    }
    return (
      <span
        className={cn(
          'bg-muted text-muted-foreground inline-flex size-8 shrink-0 items-center justify-center rounded-full text-[10px] font-medium',
          className
        )}
        aria-hidden
      >
        ?
      </span>
    )
  }
  if (dense) {
    return (
      <span
        className={cn(
          'bg-current text-muted-foreground size-3.5 shrink-0',
          className
        )}
        aria-hidden
        title={kind === 'mac' ? 'macOS' : kind === 'windows' ? 'Windows' : 'Linux'}
        style={{
          maskImage: `url(${SRC[kind]})`,
          WebkitMaskImage: `url(${SRC[kind]})`,
          maskSize: 'contain',
          WebkitMaskSize: 'contain',
          maskRepeat: 'no-repeat',
          WebkitMaskRepeat: 'no-repeat',
          maskPosition: 'center',
          WebkitMaskPosition: 'center'
        }}
      />
    )
  }
  return (
    <span
      className={cn(
        'bg-muted/80 text-foreground/85 inline-flex size-8 shrink-0 items-center justify-center rounded-full',
        className
      )}
      aria-hidden
      title={kind === 'mac' ? 'macOS' : kind === 'windows' ? 'Windows' : 'Linux'}
    >
      {/* Mask keeps Simple Icons CC0 SVGs themeable via currentColor. */}
      <span
        className="bg-current size-4"
        style={{
          maskImage: `url(${SRC[kind]})`,
          WebkitMaskImage: `url(${SRC[kind]})`,
          maskSize: 'contain',
          WebkitMaskSize: 'contain',
          maskRepeat: 'no-repeat',
          WebkitMaskRepeat: 'no-repeat',
          maskPosition: 'center',
          WebkitMaskPosition: 'center'
        }}
      />
    </span>
  )
}
