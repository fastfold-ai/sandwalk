import { Loader2, Volume2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import {
  formatBytes,
  StatusBadge,
  TtsQualityCard
} from '@/components/agents/voice/VoiceModelCards'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import {
  DEFAULT_CAPY_VOICE,
  DEFAULT_CAPY_VOICE_SPEED,
  languageCodeFromVoice,
  pickCapyVoice,
  previewPhrase,
  readCapySpeakAll,
  readCapyVoiceAuto,
  readCapyVoiceSpeed,
  voiceForDetectedText,
  writeCapySpeakAll,
  writeCapyVoice,
  writeCapyVoiceAuto,
  writeCapyVoiceSpeed
} from '@/lib/capy-voice'
import {
  browserTtsStatus,
  cancelTts,
  cancelTtsModelDownload,
  deleteTtsModel,
  downloadTtsModel,
  setActiveTtsModel,
  getTtsStatus,
  listenTtsDownloadProgress,
  listenTtsSpeakProgress,
  playTtsAudio,
  publishTtsChanged,
  speakTts,
  stopTtsPlayback,
  type DictationDownloadProgress,
  type TtsModelStatus,
  type TtsStatus,
  verifyTtsModel,
  voiceTtsReady
} from '@/lib/desktop-voice'
import { isTauri } from '@/lib/desktop'
import { pronounceForSpeech } from '@/lib/speakable-text'

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
  const [speakStatus, setSpeakStatus] = useState<string | null>(null)
  const [testPrompt, setTestPrompt] = useState(previewPhrase('en'))
  const [voiceAuto, setVoiceAuto] = useState(true)
  const [busyModel, setBusyModel] = useState<string | null>(null)
  const lastEngineRef = useRef<string | null>(null)

  const publish = (next: TtsStatus) => {
    setStatus(next)
    publishTtsChanged(next)
  }

  useEffect(() => {
    setSpeakAll(readCapySpeakAll())
    setSpeed(readCapyVoiceSpeed())
    setVoiceAuto(readCapyVoiceAuto())
    if (!desktop) {
      setStatus(browserTtsStatus())
      return
    }
    let active = true
    let unlisten = () => {}
    let unlistenSpeak = () => {}
    void listenTtsDownloadProgress(next => {
      if (active) setProgress(next)
    }).then(stop => {
      unlisten = stop
    })
    void listenTtsSpeakProgress(next => {
      if (!active) return
      if (next.phase === 'spoke') return
      setSpeakStatus(next.message)
    }).then(stop => {
      unlistenSpeak = stop
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
      unlistenSpeak()
    }
  }, [desktop])

  useEffect(() => {
    const voices = status?.voices || []
    if (!voices.length) return
    const engine = status?.active_model || null
    const next = pickCapyVoice(voices, engine || undefined)
    const engineChanged = lastEngineRef.current !== engine
    lastEngineRef.current = engine
    if (next === voice && !engineChanged) return
    setVoice(next)
    writeCapyVoice(next, engine || undefined)
    if (engineChanged || next !== voice) {
      const language =
        voices.find(item => item.id === next)?.language_code ||
        languageCodeFromVoice(next)
      setTestPrompt(previewPhrase(language))
    }
  }, [status?.voices, status?.active_model, voice])

  const download = async (modelId: string) => {
    setError(null)
    setBusyModel(modelId)
    setProgress({
      downloaded_bytes: 0,
      total_bytes:
        status?.models.find(model => model.id === modelId)?.model_bytes ||
        status?.model_bytes ||
        0
    })
    setPhase('downloading')
    try {
      const next = await downloadTtsModel(modelId)
      const total =
        next.models.find(model => model.id === modelId)?.model_bytes ||
        next.model_bytes ||
        1
      setProgress({
        downloaded_bytes: total,
        total_bytes: total,
        message: 'Installed'
      })
      publish(next)
      await new Promise(resolve => window.setTimeout(resolve, 800))
    } catch (downloadError) {
      setError(voiceError(downloadError))
      const latest = await getTtsStatus()
      if (latest) publish(latest)
    } finally {
      setPhase('idle')
      setBusyModel(null)
      setProgress(null)
    }
  }

  const useQuality = async (modelId: string) => {
    setError(null)
    try {
      publish(await setActiveTtsModel(modelId))
    } catch (activeError) {
      setError(voiceError(activeError))
    }
  }

  const repair = async (modelId: string) => {
    setError(null)
    try {
      publish(await deleteTtsModel(modelId))
      await download(modelId)
    } catch (repairError) {
      setError(voiceError(repairError))
    }
  }

  const remove = async (modelId: string) => {
    if (
      !window.confirm(
        'Remove this Capy voice quality? You can install it again later.'
      )
    ) {
      return
    }
    setError(null)
    try {
      publish(await deleteTtsModel(modelId))
      setProgress(null)
    } catch (deleteError) {
      setError(voiceError(deleteError))
    }
  }

  const applyAutoVoice = (text: string, persistPrompt = false) => {
    if (!voiceAuto) return voice
    const next = voiceForDetectedText(text, voice, status?.voices)
    if (next !== voice) {
      setVoice(next)
      writeCapyVoice(next, status?.active_model)
    }
    if (persistPrompt) setTestPrompt(text)
    return next
  }

  const selectedVoice = status?.voices.find(item => item.id === voice)
  const languageCode = selectedVoice?.language_code || 'en'

  const preview = async () => {
    if (previewing) {
      stopTtsPlayback()
      await cancelTts().catch(() => undefined)
      setPreviewing(false)
      return
    }
    if (!voiceTtsReady(status)) return
    const text = testPrompt.trim() || previewPhrase(languageCode)
    const spokenVoice = applyAutoVoice(text)
    const spokenLang =
      status?.voices.find(item => item.id === spokenVoice)?.language_code ||
      languageCode
    setError(null)
    setPreviewing(true)
    setSpeakStatus('Loading model into memory…')
    try {
      stopTtsPlayback()
      const audio = await speakTts(
        pronounceForSpeech(text, spokenLang),
        spokenVoice,
        speed
      )
      setSpeakStatus('Playing…')
      await playTtsAudio(audio)
    } catch (previewError) {
      setError(voiceError(previewError))
    } finally {
      setPreviewing(false)
      setSpeakStatus(null)
    }
  }

  const downloading = phase === 'downloading' || !!status?.download_in_progress
  const progressTotal = progress?.total_bytes || status?.model_bytes || 1
  const progressPercent = Math.min(
    100,
    Math.round(((progress?.downloaded_bytes || 0) / progressTotal) * 100)
  )
  const qualityModels: TtsModelStatus[] = status?.models?.length
    ? status.models
    : [
        {
          id: 'fp32',
          name: 'Kokoro 82M · Best',
          quality: 'FP32 · highest quality',
          model_bytes: 325_532_232,
          model_installed: false,
          model_verified: false,
          supported: true
        },
        {
          id: 'fp16',
          name: 'Kokoro 82M · Clear',
          quality: 'FP16 · recommended',
          model_bytes: 163_234_740,
          model_installed: false,
          model_verified: false,
          supported: true
        },
        {
          id: 'q8',
          name: 'Kokoro 82M · Fast',
          quality: 'Q8 · smallest',
          model_bytes: 86_033_585,
          model_installed: Boolean(status?.model_verified),
          model_verified: Boolean(status?.model_verified),
          supported: true
        }
      ]

  const kokoroModels = qualityModels.filter(model =>
    ['fp32', 'fp16', 'q8'].includes(model.id)
  )
  const mlxModels = qualityModels.filter(model =>
    ['chatterbox', 'qwen3-06', 'qwen3-17'].includes(model.id)
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
          Kokoro stays small and offline. Chatterbox and Qwen3 use MLX on
          Apple Silicon with Python 3.10–3.12.
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

      <div className="space-y-3">
        <div className="space-y-2">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {kokoroModels.map(model => (
            <TtsQualityCard
              key={model.id}
              model={model}
              active={status?.active_model === model.id && model.model_verified}
              supported={model.supported !== false && Boolean(status?.supported)}
              downloading={downloading && busyModel === model.id}
              onInstall={() => void download(model.id)}
              onCancel={() => void cancelTtsModelDownload()}
              onRepair={() => void repair(model.id)}
              onRemove={() => void remove(model.id)}
              onUse={() => void useQuality(model.id)}
            />
          ))}
          </div>
        </div>

        {mlxModels.length ? (
          <div className="space-y-2">
            <p className="text-sm font-medium">MLX engines</p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {mlxModels.map(model => (
              <TtsQualityCard
                key={model.id}
                model={model}
                active={status?.active_model === model.id && model.model_verified}
                supported={Boolean(model.supported)}
                downloading={downloading && busyModel === model.id}
                onInstall={() => void download(model.id)}
                onCancel={() => void cancelTtsModelDownload()}
                onRepair={() => void repair(model.id)}
                onRemove={() => void remove(model.id)}
                onUse={() => void useQuality(model.id)}
              />
            ))}
            </div>
          </div>
        ) : null}

        <div className="max-w-lg space-y-3">
        {downloading ? (
          <div className="rounded-xl border px-3 py-3">
            <div className="bg-muted h-2 overflow-hidden rounded-full">
              <div
                className={
                  progressPercent === 0
                    ? 'bg-foreground/80 h-full w-1/5 animate-pulse'
                    : 'bg-foreground/80 h-full transition-all'
                }
                style={
                  progressPercent === 0
                    ? undefined
                    : { width: `${progressPercent}%` }
                }
              />
            </div>
            <div className="text-muted-foreground mt-2 flex gap-3 text-xs">
              <span className="min-w-0 truncate">
                {progress?.message ||
                  (progressPercent === 0
                    ? 'Installing mlx-audio…'
                    : `${formatBytes(progress?.downloaded_bytes || 0)} of ${formatBytes(progressTotal)}`)}
              </span>
              <span className="ml-auto shrink-0 tabular-nums">
                {progressPercent === 0 ? '…' : `${progressPercent}%`}
              </span>
            </div>
            {progressPercent > 0 && progress?.message ? (
              <p className="text-muted-foreground mt-1 truncate text-xs">
                {formatBytes(progress.downloaded_bytes || 0)} of{' '}
                {formatBytes(progressTotal)}
              </p>
            ) : null}
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

        <label className="flex items-center justify-between gap-3 text-sm">
          <span>
            Match voice to language
            <span className="text-muted-foreground mt-0.5 block text-xs">
              Auto-picks a voice from the text language
            </span>
          </span>
          <input
            type="checkbox"
            className="size-4"
            checked={voiceAuto}
            onChange={event => {
              setVoiceAuto(event.target.checked)
              writeCapyVoiceAuto(event.target.checked)
            }}
          />
        </label>

        <div className="space-y-1.5">
          <label className="text-sm font-medium" htmlFor="capy-voice">
            Voice
            {selectedVoice ? (
              <span className="text-muted-foreground ml-2 font-normal">
                {selectedVoice.language}
              </span>
            ) : null}
          </label>
          <select
            id="capy-voice"
            className="border-input bg-background h-9 w-full rounded-md border px-2 text-sm"
            value={voice}
            disabled={!status?.voices.length}
            onChange={event => {
              const next = event.target.value
              setVoice(next)
              writeCapyVoice(next, status?.active_model)
              writeCapyVoiceAuto(false)
              setVoiceAuto(false)
              const nextLang =
                status?.voices.find(item => item.id === next)?.language_code ||
                'en'
              setTestPrompt(previewPhrase(nextLang))
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

        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-medium">Capy voice test</h4>
            {voiceTtsReady(status) ? (
              <StatusBadge tone="ok" label="Ready" />
            ) : null}
          </div>
          <p className="text-muted-foreground text-xs">
            Play a short Capy line with the selected voice.
          </p>
          <textarea
            id="capy-voice-test-prompt"
            className="border-input bg-background min-h-20 w-full rounded-md border px-3 py-2 text-sm"
            value={testPrompt}
            maxLength={800}
            onChange={event => {
              const next = event.target.value
              setTestPrompt(next)
              applyAutoVoice(next)
            }}
            placeholder={previewPhrase(languageCode)}
            disabled={!voiceTtsReady(status)}
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              disabled={!voiceTtsReady(status) || (!previewing && !testPrompt.trim())}
              onClick={() => void preview()}
            >
              {previewing && speakStatus && speakStatus !== 'Playing…' ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Volume2 className="size-3.5" />
              )}
              {previewing ? 'Stop' : 'Test Capy voice'}
            </Button>
            {previewing && speakStatus ? (
              <p className="text-muted-foreground text-xs" role="status">
                {speakStatus}
                {speakStatus === 'Loading model into memory…'
                  ? ' First load can take a minute.'
                  : null}
              </p>
            ) : null}
          </div>
        </div>
        </div>
      </div>
    </section>
  )
}
