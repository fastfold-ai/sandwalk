import { Pause, Play } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

type VideoPlayMode = 'card' | 'thumb' | 'panel'

/**
 * Video preview with centered play/pause.
 * - card: chat inline, natural aspect (no letterbox)
 * - thumb: fills parent with cover crop (artifacts grid)
 * - panel: fits inside parent without overflow (file preview)
 */
export function VideoPlayPreview({
  src,
  className,
  mode = 'card',
  muted = false,
  onError
}: {
  src: string
  className?: string
  mode?: VideoPlayMode
  muted?: boolean
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
      video.currentTime = 0
    }
  }, [src])

  const toggle = async () => {
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

  const ratio = aspect ?? 9 / 16

  const playOverlay = (
    <div
      role="presentation"
      className={cn(
        'absolute inset-0 z-10 flex items-center justify-center transition-opacity duration-200',
        playing ? 'opacity-0 hover:opacity-100' : 'opacity-100'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        void toggle()
      }}
    >
      <span
        className={cn(
          'relative grid size-12 place-items-center rounded-full',
          'bg-white/18 text-white shadow-[0_8px_32px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.45)]',
          'ring-1 ring-white/40 backdrop-blur-xl backdrop-saturate-150',
          'transition-transform duration-200 hover:scale-105 active:scale-95',
          'before:pointer-events-none before:absolute before:inset-0 before:rounded-full',
          'before:bg-gradient-to-b before:from-white/35 before:to-transparent before:opacity-80'
        )}
        aria-hidden
      >
        {playing ? (
          <Pause className="relative size-4 fill-current drop-shadow-sm" />
        ) : (
          <Play className="relative ml-0.5 size-4 fill-current drop-shadow-sm" />
        )}
      </span>
      <span className="sr-only">{playing ? 'Pause video' : 'Play video'}</span>
    </div>
  )

  if (mode === 'panel') {
    return (
      <div
        className={cn(
          'relative max-h-full max-w-full overflow-hidden rounded-lg',
          className
        )}
      >
        <video
          ref={videoRef}
          src={src}
          playsInline
          preload="metadata"
          muted={muted}
          className="block max-h-full max-w-full object-contain"
          onLoadedMetadata={event => {
            const el = event.currentTarget
            if (el.videoWidth > 0 && el.videoHeight > 0) {
              setAspect(el.videoWidth / el.videoHeight)
            }
            setReady(true)
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
          onError={() => onError?.()}
          onClick={event => {
            event.stopPropagation()
            void toggle()
          }}
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
        ref={videoRef}
        src={src}
        playsInline
        preload="metadata"
        muted={muted}
        className={cn(
          'h-full w-full',
          mode === 'thumb' ? 'object-cover' : 'object-contain'
        )}
        onLoadedMetadata={event => {
          const el = event.currentTarget
          if (el.videoWidth > 0 && el.videoHeight > 0) {
            setAspect(el.videoWidth / el.videoHeight)
          }
          setReady(true)
        }}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onError={() => onError?.()}
        onClick={event => {
          event.stopPropagation()
          void toggle()
        }}
      />

      {!ready ? (
        <div className="bg-muted/40 absolute inset-0 animate-pulse" aria-hidden />
      ) : null}

      {playOverlay}
    </div>
  )
}
