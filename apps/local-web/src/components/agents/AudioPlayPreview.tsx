import { Pause, Play } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

type AudioPlayMode = 'card' | 'thumb' | 'panel'

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

const glassBtn =
  'relative grid place-items-center rounded-full ' +
  'bg-white/18 text-white shadow-[0_8px_32px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.45)] ' +
  'ring-1 ring-white/40 backdrop-blur-xl backdrop-saturate-150 ' +
  'transition-transform duration-200 hover:scale-105 active:scale-95 ' +
  'before:pointer-events-none before:absolute before:inset-0 before:rounded-full ' +
  'before:bg-gradient-to-b before:from-white/35 before:to-transparent before:opacity-80'

/**
 * Compact audio player card with glassy play/pause.
 * - card: chat inline
 * - thumb: artifacts grid tile
 * - panel: full file preview
 */
export function AudioPlayPreview({
  src,
  title,
  className,
  mode = 'card',
  onError,
  onOpen
}: {
  src: string
  title?: string
  className?: string
  mode?: AudioPlayMode
  onError?: () => void
  onOpen?: () => void
}) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [ready, setReady] = useState(false)
  const [current, setCurrent] = useState(0)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    setPlaying(false)
    setReady(false)
    setCurrent(0)
    setDuration(0)
    const audio = audioRef.current
    if (audio) {
      audio.pause()
      audio.currentTime = 0
    }
  }, [src])

  const toggle = async () => {
    const audio = audioRef.current
    if (!audio) return
    if (audio.paused) {
      try {
        await audio.play()
        setPlaying(true)
      } catch {
        // ignore play failures
      }
    } else {
      audio.pause()
      setPlaying(false)
    }
  }

  const progress = duration > 0 ? Math.min(1, current / duration) : 0
  const compact = mode === 'thumb'

  return (
    <div
      className={cn(
        'bg-muted/40 border-border/50 relative overflow-hidden rounded-xl border',
        mode === 'card' && 'w-full max-w-[18rem]',
        mode === 'thumb' && 'flex h-full w-full flex-col justify-center rounded-none border-0',
        mode === 'panel' && 'w-full max-w-md',
        className
      )}
    >
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        className="hidden"
        onLoadedMetadata={event => {
          setDuration(event.currentTarget.duration || 0)
          setReady(true)
        }}
        onTimeUpdate={event => setCurrent(event.currentTarget.currentTime || 0)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false)
          setCurrent(0)
        }}
        onError={() => onError?.()}
      />

      {/* Soft waveform-ish backdrop */}
      <div
        className="pointer-events-none absolute inset-0 opacity-70"
        aria-hidden
        style={{
          background:
            'radial-gradient(120% 80% at 20% 40%, rgba(255,255,255,0.16), transparent 55%), ' +
            'linear-gradient(135deg, rgba(15,23,42,0.08), rgba(16,185,129,0.12) 55%, rgba(0,0,0,0.04))'
        }}
      />

      <div
        className={cn(
          'relative flex items-center gap-3',
          compact ? 'px-3 py-3' : 'px-3.5 py-3'
        )}
      >
        <button
          type="button"
          className={cn(glassBtn, compact ? 'size-10' : 'size-11')}
          onClick={event => {
            event.preventDefault()
            event.stopPropagation()
            void toggle()
          }}
          aria-label={playing ? 'Pause audio' : 'Play audio'}
        >
          {playing ? (
            <Pause className="relative size-4 fill-current drop-shadow-sm" />
          ) : (
            <Play className="relative ml-0.5 size-4 fill-current drop-shadow-sm" />
          )}
        </button>

        <div className="min-w-0 flex-1">
          {title ? (
            onOpen ? (
              <button
                type="button"
                className="text-foreground hover:text-foreground/80 mb-1 block w-full truncate text-left text-xs font-medium"
                title={title}
                onClick={event => {
                  event.stopPropagation()
                  onOpen()
                }}
              >
                {title}
              </button>
            ) : (
              <div className="text-foreground mb-1 truncate text-xs font-medium">
                {title}
              </div>
            )
          ) : null}

          <div
            className="bg-foreground/10 relative h-1 cursor-pointer overflow-hidden rounded-full"
            onClick={event => {
              event.stopPropagation()
              const audio = audioRef.current
              if (!audio || !duration) return
              const rect = event.currentTarget.getBoundingClientRect()
              const ratio = Math.min(
                1,
                Math.max(0, (event.clientX - rect.left) / rect.width)
              )
              audio.currentTime = ratio * duration
              setCurrent(audio.currentTime)
            }}
          >
            <div
              className="bg-foreground/70 absolute inset-y-0 left-0 rounded-full transition-[width] duration-75"
              style={{ width: `${progress * 100}%` }}
            />
          </div>

          <div className="text-muted-foreground mt-1 flex justify-between text-[10px] tabular-nums">
            <span>{ready ? formatTime(current) : '—'}</span>
            <span>{ready ? formatTime(duration) : '—'}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
