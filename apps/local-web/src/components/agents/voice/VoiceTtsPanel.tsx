import { ChevronDown, Volume2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import {
  formatBytes,
  StatusBadge
} from '@/components/agents/voice/VoiceModelCards'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Slider } from '@/components/ui/slider'
import {
  DEFAULT_CAPY_VOICE,
  DEFAULT_CAPY_VOICE_SPEED,
  previewPhrase,
  readCapySpeakAll,
  readCapyVoice,
  readCapyVoiceSpeed,
  writeCapySpeakAll,
  writeCapyVoice,
  writeCapyVoiceSpeed
} from '@/lib/capy-voice'
import {
  browserTtsStatus,
  cancelTts,
  cancelTtsModelDownload,
  deleteTtsModel,
  downloadTtsModel,
  getTtsStatus,
  listenTtsDownloadProgress,
  playTtsAudio,
  publishTtsChanged,
  speakTts,
  stopTtsPlayback,
  type DictationDownloadProgress,
  type TtsStatus,
  verifyTtsModel,
  voiceTtsReady
} from '@/lib/desktop-voice'
import { isTauri } from '@/lib/desktop'

function voiceError(error: unknown) {
  if (error instanceof Error) return error.message
  return String(error)
}

export function VoiceTtsPanel() {
  const desktop = isTauri()
  const [status, setStatus] = useState<TtsStatus | null>(null)
  const [progress, setProgress] = useState<DictationDownloadProgress | null>(
    null
  )
  const [phase, setPhase] = useState<'idle' | 'downloading' | 'verifying'>(
    'idle'
  )
  const [error, setError] = useState<string | null>(null)
  const [speakAll, setSpeakAll] = useState(false)
  const [voice, setVoice] = useState(DEFAULT_CAPY_VOICE)
  const [speed, setSpeed] = useState(DEFAULT_CAPY_VOICE_SPEED)
  const [previewing, setPreviewing] = useState(false)

  const publish = (next: TtsStatus) => {
    setStatus(next)
    publishTtsChanged(next)
  }

  useEffect(() => {
    setSpeakAll(readCapySpeakAll())
    setVoice(readCapyVoice())
    setSpeed(readCapyVoiceSpeed())
    if (!desktop) {
      setStatus(browserTtsStatus())
      return
    }
    let active = true
    let unlisten = () => {}
    void listenTtsDownloadProgress(next => {
      if (active) setProgress(next)
    }).then(stop => {
      unlisten = stop
    })
    void getTtsStatus().then(async initial => {
      if (!active || !initial) return
      publish(initial)
      if (initial.model_installed && !initial.model_verified) {
        setPhase('verifying')
        try {
          publish(await verifyTtsModel())
        } catch (verifyError) {
          if (active) setError(voiceError(verifyError))
        } finally {
          if (active) setPhase('idle')
        }
      }
    })
    return () => {
      active = false
      unlisten()
    }
  }, [desktop])

  const download = async () => {
    setError(null)
    setProgress({ downloaded_bytes: 0, total_bytes: status?.model_bytes || 0 })
    setPhase('downloading')
    try {
      publish(await downloadTtsModel())
    } catch (downloadError) {
      setError(voiceError(downloadError))
      const latest = await getTtsStatus()
      if (latest) publish(latest)
    } finally {
      setPhase('idle')
    }
  }

  const remove = async () => {
    if (
      !window.confirm(
        'Remove the Capy voice model? You’ll need to install it again before Capy can speak.'
      )
    ) {
      return
    }
    setError(null)
    try {
      publish(await deleteTtsModel())
      setProgress(null)
    } catch (deleteError) {
      setError(voiceError(deleteError))
    }
  }

  const preview = async () => {
    if (!voiceTtsReady(status)) return
    setError(null)
    setPreviewing(true)
    try {
      stopTtsPlayback()
      await cancelTts().catch(() => undefined)
      const selected = status?.voices.find(item => item.id === voice)
      const audio = await speakTts(
        previewPhrase(selected?.language_code || 'en'),
        voice,
        speed
      )
      await playTtsAudio(audio)
    } catch (previewError) {
      setError(voiceError(previewError))
    } finally {
      setPreviewing(false)
    }
  }

  const downloading = phase === 'downloading' || !!status?.download_in_progress
  const progressTotal = progress?.total_bytes || status?.model_bytes || 1
  const progressPercent = Math.min(
    100,
    Math.round(((progress?.downloaded_bytes || 0) / progressTotal) * 100)
  )
  const groups = useMemo(() => {
    const map = new Map<string, NonNullable<TtsStatus['voices']>>()
    for (const item of status?.voices || []) {
      const list = map.get(item.group) || []
      list.push(item)
      map.set(item.group, list)
    }
    return [...map.entries()]
  }, [status?.voices])

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-base font-semibold">Voice Capy Model response</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          Local Kokoro model so Capy can speak short replies. Quality varies by
          language.
        </p>
      </div>
      {error ? (
        <div
          role="alert"
          className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm"
        >
          {error}
        </div>
      ) : null}

      <div className="max-w-lg space-y-3">
        <div className="flex items-center gap-3 rounded-xl border px-3 py-3">
          <span className="bg-muted/50 grid size-9 shrink-0 place-items-center rounded-lg">
            <Volume2 className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">Kokoro 82M · local</div>
            <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-1.5">
              {status?.supported ? (
                <StatusBadge tone="ok" label="Supported" />
              ) : (
                <StatusBadge tone="bad" label="Desktop only" />
              )}
              {status?.model_verified ? (
                <StatusBadge tone="ok" label="Ready" />
              ) : null}
              <span className="text-muted-foreground truncate text-xs">
                {formatBytes(status?.model_bytes || 86_033_585)} ·{' '}
                {status?.voices_installed || 0}/{status?.voice_count || 0} voices
              </span>
            </div>
          </div>
          <div className="flex shrink-0 items-center">
            {status?.model_verified ? (
              <div className="flex items-stretch">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-r-none border-r-0"
                  onClick={() => void download()}
                >
                  Re-download
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-l-none px-2"
                      aria-label="More Capy voice actions"
                    >
                      <ChevronDown className="size-3.5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => void remove()}
                    >
                      Remove
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ) : downloading ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => void cancelTtsModelDownload()}
              >
                Cancel
              </Button>
            ) : phase === 'verifying' ? (
              <StatusBadge tone="warn" label="Checking…" />
            ) : (
              <Button size="sm" disabled={!desktop} onClick={() => void download()}>
                Install
              </Button>
            )}
          </div>
        </div>

        {downloading ? (
          <div className="rounded-xl border px-3 py-3">
            <div className="bg-muted h-2 overflow-hidden rounded-full">
              <div
                className="bg-foreground/80 h-full transition-all"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="text-muted-foreground mt-2 flex text-xs">
              <span>
                {formatBytes(progress?.downloaded_bytes || 0)} of{' '}
                {formatBytes(progressTotal)}
              </span>
              <span className="ml-auto tabular-nums">{progressPercent}%</span>
            </div>
          </div>
        ) : null}

        <label className="flex items-center justify-between gap-3 text-sm">
          <span>
            Speak all Capy replies
            <span className="text-muted-foreground mt-0.5 block text-xs">
              Off: only after Ctrl+Ctrl or the mic
            </span>
          </span>
          <input
            type="checkbox"
            className="size-4"
            checked={speakAll}
            onChange={event => {
              setSpeakAll(event.target.checked)
              writeCapySpeakAll(event.target.checked)
            }}
          />
        </label>

        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="capy-voice">
            Voice
          </label>
          <select
            id="capy-voice"
            className="border-input bg-background h-9 w-full rounded-md border px-2 text-sm"
            value={voice}
            disabled={!status?.voices.length}
            onChange={event => {
              setVoice(event.target.value)
              writeCapyVoice(event.target.value)
              stopTtsPlayback()
            }}
          >
            {groups.map(([group, voices]) => (
              <optgroup key={group} label={group}>
                {voices.map(item => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Speed</span>
            <span className="text-muted-foreground tabular-nums">
              {speed.toFixed(1)}×
            </span>
          </div>
          <Slider
            min={0.5}
            max={2}
            step={0.1}
            value={[speed]}
            onValueChange={value => {
              const next = value[0] ?? 1
              setSpeed(next)
              writeCapyVoiceSpeed(next)
            }}
          />
        </div>

        <Button
          variant="outline"
          size="sm"
          disabled={!voiceTtsReady(status) || previewing}
          onClick={() => void preview()}
        >
          {previewing ? 'Playing…' : 'Preview'}
        </Button>
      </div>
    </section>
  )
}
