import { ChevronDown, HardDrive, Mic, Monitor } from 'lucide-react'
import { useEffect, useState } from 'react'

import { VoiceLevelBars } from '@/components/agents/composer/VoiceLevelBars'
import { DesktopOnlyCallout } from '@/components/agents/DesktopOnlyCallout'
import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { isTauri } from '@/lib/desktop'
import {
  browserDictationStatus,
  cancelDictationModelDownload,
  deleteDictationModel,
  type DictationDownloadProgress,
  type DictationStatus,
  downloadDictationModel,
  getDictationLevel,
  getDictationStatus,
  listenDictationDownloadProgress,
  markDictationTestPassed,
  publishVoiceInputChanged,
  startDictation,
  stopDictation,
  verifyDictationModel,
  voiceReady
} from '@/lib/desktop-voice'
import { cn } from '@/lib/utils'

const OPENAI_ICON = INTEGRATION_ICONS.openai

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KiB`
  return `${(bytes / (1024 * 1024)).toFixed(0)} MiB`
}

function voiceError(error: unknown) {
  if (error instanceof Error) return error.message
  return String(error)
}

function StatusBadge({
  tone,
  label
}: {
  tone: 'neutral' | 'ok' | 'warn' | 'bad'
  label: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[10px] font-medium',
        tone === 'neutral' && 'bg-muted text-muted-foreground',
        tone === 'ok' && 'bg-sky-500/12 text-sky-700 dark:text-sky-300',
        tone === 'warn' && 'bg-amber-500/12 text-amber-700 dark:text-amber-300',
        tone === 'bad' && 'bg-destructive/10 text-destructive'
      )}
    >
      <span
        className={cn(
          'size-1.5 shrink-0 rounded-full',
          tone === 'neutral' && 'bg-muted-foreground/50',
          tone === 'ok' && 'bg-sky-500',
          tone === 'warn' && 'bg-amber-500',
          tone === 'bad' && 'bg-destructive'
        )}
        aria-hidden
      />
      {label}
    </span>
  )
}

export function VoiceView() {
  const desktop = isTauri()
  const [status, setStatus] = useState<DictationStatus | null>(null)
  const [progress, setProgress] = useState<DictationDownloadProgress | null>(
    null
  )
  const [phase, setPhase] = useState<
    'idle' | 'downloading' | 'verifying' | 'testing' | 'transcribing'
  >('idle')
  const [error, setError] = useState<string | null>(null)
  const [testTranscript, setTestTranscript] = useState('')
  const [levels, setLevels] = useState<number[]>([])

  const publish = (next: DictationStatus) => {
    setStatus(next)
    publishVoiceInputChanged(next)
  }

  useEffect(() => {
    if (!desktop) {
      setStatus(browserDictationStatus())
      return
    }
    let active = true
    let unlisten = () => {}
    void listenDictationDownloadProgress(next => {
      if (active) setProgress(next)
    }).then(stop => {
      unlisten = stop
    })
    void getDictationStatus().then(async initial => {
      if (!active || !initial) return
      publish(initial)
      if (initial.model_installed && !initial.model_verified) {
        setPhase('verifying')
        try {
          const verified = await verifyDictationModel()
          if (active) publish(verified)
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

  useEffect(() => {
    if (!status?.recording) {
      setLevels([])
      return
    }
    const timer = window.setInterval(() => {
      void getDictationLevel().then(level => {
        if (typeof level === 'number') {
          setLevels(cur => [...cur.slice(-13), level])
        }
      })
    }, 100)
    return () => window.clearInterval(timer)
  }, [status?.recording])

  const download = async () => {
    setError(null)
    setProgress({
      downloaded_bytes: 0,
      total_bytes: status?.model_bytes || 0
    })
    setPhase('downloading')
    try {
      publish(await downloadDictationModel())
    } catch (downloadError) {
      setError(voiceError(downloadError))
      const latest = await getDictationStatus()
      if (latest) publish(latest)
    } finally {
      setPhase('idle')
    }
  }

  const cancelDownload = async () => {
    await cancelDictationModelDownload().catch(() => undefined)
  }

  const repair = async () => {
    setError(null)
    try {
      publish(await deleteDictationModel())
      await download()
    } catch (repairError) {
      setError(voiceError(repairError))
    }
  }

  const remove = async () => {
    if (
      !window.confirm(
        'Remove the speech model? You’ll need to install it again before using the mic.'
      )
    ) {
      return
    }
    setError(null)
    try {
      publish(await deleteDictationModel())
      setTestTranscript('')
      setProgress(null)
    } catch (deleteError) {
      setError(voiceError(deleteError))
    }
  }

  const toggleTest = async () => {
    if (!status?.supported || !status.model_verified) return
    setError(null)
    try {
      if (status.recording) {
        setPhase('transcribing')
        const transcript = (await stopDictation()).trim()
        setTestTranscript(transcript)
        if (!transcript) {
          throw new Error(
            'Didn’t catch that — try speaking a bit longer and try again.'
          )
        }
        publish(await markDictationTestPassed())
      } else {
        setTestTranscript('')
        setPhase('testing')
        publish(await startDictation())
      }
    } catch (testError) {
      setError(voiceError(testError))
      const latest = await getDictationStatus()
      if (latest) publish(latest)
    } finally {
      setPhase('idle')
    }
  }

  const downloading = phase === 'downloading' || !!status?.download_in_progress
  const progressTotal = progress?.total_bytes || status?.model_bytes || 1
  const progressPercent = Math.min(
    100,
    Math.round(((progress?.downloaded_bytes || 0) / progressTotal) * 100)
  )
  const ready = voiceReady(status)
  const modelBytes = status?.model_bytes || 147_964_211

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl space-y-8 p-4 md:p-6">
        <div>
          <h2 className="text-2xl font-semibold">Voice</h2>
          <p className="text-muted-foreground mt-2 max-w-2xl text-sm">
            Local voice to chat with your agents
          </p>
        </div>

        {!desktop ? (
          <DesktopOnlyCallout feature="Voice setup" />
        ) : (
          <>
            {error ? (
              <div
                role="alert"
                className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm"
              >
                {error}
              </div>
            ) : null}

            <section className="space-y-3">
              <div>
                <h3 className="text-base font-semibold">Speech to text</h3>
                <p className="text-muted-foreground mt-1 text-sm">
                  STT models — we’ll add more here over time.
                </p>
              </div>
              {status?.compatibility_reason ? (
                <p className="text-destructive text-sm">
                  {status.compatibility_reason}
                </p>
              ) : null}

              <div className="max-w-lg">
                <div className="flex items-center gap-3 rounded-xl border px-3 py-3">
                  <span className="bg-muted/50 grid size-9 shrink-0 place-items-center rounded-lg">
                    {OPENAI_ICON ? (
                      <img
                        src={OPENAI_ICON.src}
                        alt=""
                        className={cn(
                          'size-6 object-contain',
                          OPENAI_ICON.invertInDark && 'dark:invert'
                        )}
                      />
                    ) : (
                      <Monitor className="size-4" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">
                      Whisper Base · English
                    </div>
                    <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-1.5">
                      {status ? (
                        <StatusBadge
                          tone={status.supported ? 'ok' : 'bad'}
                          label={
                            status.supported ? 'Supported' : 'Unsupported'
                          }
                        />
                      ) : null}
                      {status?.model_verified ? (
                        <StatusBadge tone="ok" label="Ready" />
                      ) : null}
                      <span className="text-muted-foreground truncate text-xs">
                        {status?.model_verified
                          ? formatBytes(modelBytes)
                          : `OpenAI · local · ${formatBytes(modelBytes)}`}
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
                          onClick={() => void repair()}
                        >
                          Re-download
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-l-none px-2"
                              aria-label="More model actions"
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
                        onClick={() => void cancelDownload()}
                      >
                        Cancel
                      </Button>
                    ) : phase === 'verifying' ? (
                      <StatusBadge tone="warn" label="Checking…" />
                    ) : (
                      <Button
                        size="sm"
                        disabled={!status?.supported}
                        onClick={() => void download()}
                      >
                        Install
                      </Button>
                    )}
                  </div>
                </div>

                {downloading ? (
                  <div className="mt-2 rounded-xl border px-3 py-3">
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
                      <span className="ml-auto tabular-nums">
                        {progressPercent}%
                      </span>
                    </div>
                  </div>
                ) : null}
              </div>
            </section>

            <section className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-base font-semibold">Mic check</h3>
                {ready ? <StatusBadge tone="ok" label="Enabled" /> : null}
              </div>
              <p className="text-muted-foreground text-sm">
                {ready
                  ? 'You’re set — the composer mic is available.'
                  : 'Say a short phrase so we can turn the composer mic on.'}
              </p>
              <Button
                variant="outline"
                size="sm"
                disabled={
                  !status?.supported ||
                  !status?.model_verified ||
                  phase === 'transcribing'
                }
                onClick={() => void toggleTest()}
              >
                <Mic className="size-3.5" />
                {status?.recording
                  ? 'Stop & confirm'
                  : phase === 'transcribing'
                    ? 'Transcribing…'
                    : ready
                      ? 'Test again'
                      : 'Start check'}
              </Button>

              {status?.recording || phase === 'transcribing' ? (
                <p
                  className="text-muted-foreground flex items-center gap-2.5 text-sm"
                  role="status"
                >
                  {phase === 'transcribing' ? (
                    <span className="text-muted-foreground">Transcribing…</span>
                  ) : (
                    <>
                      <VoiceLevelBars
                        levels={levels}
                        className="text-muted-foreground"
                      />
                      <span>Listening…</span>
                    </>
                  )}
                </p>
              ) : null}

              {testTranscript ? (
                <p className="text-sm">
                  <span className="text-muted-foreground">Heard: </span>
                  {testTranscript}
                </p>
              ) : null}
            </section>

            <section className="text-muted-foreground space-y-3 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <Monitor className="size-3.5 shrink-0" />
                <span>{status?.device_summary || 'This machine'}</span>
              </div>
              <dl className="grid max-w-lg grid-cols-2 gap-x-6 gap-y-2">
                <div>
                  <dt className="text-foreground/70 font-medium">macOS</dt>
                  <dd>12+ · Apple Silicon</dd>
                </div>
                <div>
                  <dt className="text-foreground/70 font-medium">Windows</dt>
                  <dd>10 22H2 / 11 · x64</dd>
                </div>
                <div>
                  <dt className="text-foreground/70 font-medium">Memory</dt>
                  <dd>8 GB recommended</dd>
                </div>
                <div>
                  <dt className="text-foreground/70 font-medium">CPU</dt>
                  <dd>4 cores recommended</dd>
                </div>
              </dl>
              <p className="flex items-center gap-2">
                <HardDrive className="size-3.5 shrink-0" />
                Models saved in Sandwalk app data{' '}
                <code className="font-mono text-[11px]">models/</code>
              </p>
            </section>
          </>
        )}
      </div>
    </ScrollArea>
  )
}
