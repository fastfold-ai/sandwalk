import { Mic } from 'lucide-react'
import { useEffect, useState } from 'react'

import { VoiceLevelBars } from '@/components/agents/composer/VoiceLevelBars'
import { DesktopOnlyCallout } from '@/components/agents/DesktopOnlyCallout'
import {
  formatBytes,
  StatusBadge,
  SttModelCard
} from '@/components/agents/voice/VoiceModelCards'
import { VoiceTtsPanel } from '@/components/agents/voice/VoiceTtsPanel'
import { Button } from '@/components/ui/button'
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
  type SttModelStatus,
  verifyDictationModel,
  voiceReady
} from '@/lib/desktop-voice'

function voiceError(error: unknown) {
  if (error instanceof Error) return error.message
  return String(error)
}

function fallbackSttModels(status: DictationStatus): SttModelStatus[] {
  const models = (status.models || []).filter(model => model.id !== 'en')
  if (models.length) return models
  return [
    {
      id: 'multi',
      model_name: status.model_name || 'Whisper Base Multilingual (local)',
      model_bytes: status.model_bytes || 147_951_465,
      model_installed: status.model_installed,
      model_verified: status.model_verified,
      test_passed: status.test_passed
    }
  ]
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
      total_bytes: status?.model_bytes || 147_951_465
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
  const sttModels = status ? fallbackSttModels(status) : []

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl space-y-8 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
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
                  One local Whisper model for English and other languages.
                </p>
              </div>
              {status?.compatibility_reason ? (
                <p className="text-destructive text-sm">
                  {status.compatibility_reason}
                </p>
              ) : null}

              <div className="space-y-2">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {sttModels.map(model => (
                  <SttModelCard
                    key={model.id}
                    model={model}
                    active={Boolean(model.model_verified)}
                    supported={Boolean(status?.supported)}
                    downloading={downloading}
                    verifying={phase === 'verifying'}
                    onInstall={() => void download()}
                    onCancel={() => void cancelDownload()}
                    onRepair={() => void repair()}
                    onRemove={() => void remove()}
                  />
                ))}
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
                      <span className="ml-auto tabular-nums">
                        {progressPercent}%
                      </span>
                    </div>
                  </div>
                ) : null}
              </div>
            </section>

            <VoiceTtsPanel />

            <section className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
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
          </>
        )}
      </div>
    </ScrollArea>
  )
}
