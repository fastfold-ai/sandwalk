import { Pause, Play } from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
  type MouseEvent,
  type SyntheticEvent
} from 'react'

import { cn } from '@/lib/utils'

type VideoPlayMode = 'card' | 'thumb' | 'panel'

/** Seek past t=0 so browsers decode a visible poster frame (metadata-only is often black). */
export function seekVideoPosterFrame(video: HTMLVideoElement) {
  const duration = video.duration
  const target =
    Number.isFinite(duration) && duration > 0
      ? Math.min(0.1, Math.max(0.001, duration * 0.01))
      : 0.001
  try {
    if (Math.abs(video.currentTime - target) > 0.0005) {
      video.currentTime = target
    }
  } catch {
    // Some sources reject seeks until more data arrives.
  }
}

/**
 * Video preview with centered play/pause.
 * - card: chat inline, natural aspect (no letterbox)
 * - thumb: fills parent with cover crop (artifacts grid / library / composer)
 * - panel: fits inside parent without overflow (file preview)
 */
export function VideoPlayPreview({
  src,
  className,
  mode = 'card',
  muted = false,
  interactive = true,
  onError
}: {
  src: string
  className?: string
  mode?: VideoPlayMode
  muted?: boolean
  /** When false, show a frame + play badge but don't toggle playback. */
  interactive?: boolean
  onError?: () => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [ready, setReady] = useState(false)
  const [aspect, setAspect] = useState<number | null>(null)

  useEffect(() => {
    setPlaying(false)
    setReady(false)
    setAspect(null)
    const video = videoRef.current
    if (video) {
      video.pause()
    }
  }, [src])

  const toggle = async () => {
    if (!interactive) return
    const video = videoRef.current
    if (!video) return
    if (video.paused) {
      try {
        await video.play()
        setPlaying(true)
      } catch {
        // Autoplay/play may fail; keep overlay.
      }
    } else {
      video.pause()
      setPlaying(false)
    }
  }

  const onMeta = (el: HTMLVideoElement) => {
    if (el.videoWidth > 0 && el.videoHeight > 0) {
      setAspect(el.videoWidth / el.videoHeight)
    }
    seekVideoPosterFrame(el)
    // If seek is a no-op / already painted, mark ready immediately.
    if (el.readyState >= 2) setReady(true)
  }

  const ratio = aspect ?? 9 / 16
  const overlaySize = mode === 'thumb' ? 'size-8' : 'size-12'
  const iconSize = mode === 'thumb' ? 'size-3' : 'size-4'

  const playOverlay = (
    <div
      role="presentation"
      className={cn(
        'absolute inset-0 z-10 flex items-center justify-center transition-opacity duration-200',
        playing ? 'opacity-0 hover:opacity-100' : 'opacity-100',
        !interactive && 'pointer-events-none'
      )}
      onClick={
        interactive
          ? event => {
              event.preventDefault()
              event.stopPropagation()
              void toggle()
            }
          : undefined
      }
    >
      <span
        className={cn(
          'relative grid place-items-center rounded-full',
          overlaySize,
          'bg-white/18 text-white shadow-[0_8px_32px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.45)]',
          'ring-1 ring-white/40 backdrop-blur-xl backdrop-saturate-150',
          interactive &&
            'transition-transform duration-200 hover:scale-105 active:scale-95',
          'before:pointer-events-none before:absolute before:inset-0 before:rounded-full',
          'before:bg-gradient-to-b before:from-white/35 before:to-transparent before:opacity-80'
        )}
        aria-hidden
      >
        {playing ? (
          <Pause
            className={cn('relative fill-current drop-shadow-sm', iconSize)}
          />
        ) : (
          <Play
            className={cn(
              'relative ml-0.5 fill-current drop-shadow-sm',
              iconSize
            )}
          />
        )}
      </span>
      {interactive ? (
        <span className="sr-only">{playing ? 'Pause video' : 'Play video'}</span>
      ) : null}
    </div>
  )

  const videoProps = {
    ref: videoRef,
    src,
    playsInline: true as const,
    preload: 'metadata' as const,
    muted,
    onLoadedMetadata: (event: SyntheticEvent<HTMLVideoElement>) => {
      onMeta(event.currentTarget)
    },
    onLoadedData: (event: SyntheticEvent<HTMLVideoElement>) => {
      seekVideoPosterFrame(event.currentTarget)
      setReady(true)
    },
    onSeeked: () => setReady(true),
    onPlay: () => setPlaying(true),
    onPause: () => setPlaying(false),
    onEnded: () => setPlaying(false),
    onError: () => onError?.(),
    onClick: interactive
      ? (event: MouseEvent<HTMLVideoElement>) => {
          event.stopPropagation()
          void toggle()
        }
      : undefined
  }

  if (mode === 'panel') {
    return (
      <div
        className={cn(
          'relative max-h-full max-w-full overflow-hidden rounded-lg',
          className
        )}
      >
        <video
          {...videoProps}
          className="block max-h-full max-w-full object-contain"
        />
        {!ready ? (
          <div
            className="bg-muted/40 absolute inset-0 animate-pulse rounded-lg"
            aria-hidden
          />
        ) : null}
        {playOverlay}
      </div>
    )
  }

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-lg',
        mode === 'thumb' && 'h-full w-full rounded-none',
        mode === 'card' && 'max-h-64 w-auto max-w-[14rem]',
        className
      )}
      style={
        mode === 'thumb'
          ? undefined
          : {
              aspectRatio: String(ratio),
              width: 'min(14rem, 100%)'
            }
      }
    >
      <video
        {...videoProps}
        className={cn(
          'h-full w-full',
          mode === 'thumb' ? 'object-cover' : 'object-contain'
        )}
      />

      {!ready ? (
        <div className="bg-muted/40 absolute inset-0 animate-pulse" aria-hidden />
      ) : null}

      {playOverlay}
    </div>
  )
}
