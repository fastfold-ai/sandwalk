/**
 * Local dictation bridge (desktop Tauri only). Browser builds soft-fail —
 * Voice Input stays unavailable rather than sending mic audio to a server.
 */

import { isTauri } from '@/lib/desktop'

export type SttModelStatus = {
  id: string
  model_name: string
  model_bytes: number
  model_installed: boolean
  model_verified: boolean
  test_passed: boolean
}

export type DictationStatus = {
  recording: boolean
  model_installed: boolean
  model_verified: boolean
  test_passed: boolean
  download_in_progress: boolean
  model_name: string
  model_bytes: number
  active_model: string
  models: SttModelStatus[]
  supported: boolean
  device_summary: string
  compatibility_reason: string | null
}

export type TtsVoiceInfo = {
  id: string
  label: string
  group: string
  language: string
  language_code: string
}

export type TtsModelStatus = {
  id: string
  name: string
  quality: string
  model_bytes: number
  model_installed: boolean
  model_verified: boolean
  supported: boolean
}

export type TtsStatus = {
  model_installed: boolean
  model_verified: boolean
  download_in_progress: boolean
  model_name: string
  model_bytes: number
  active_model: string
  models: TtsModelStatus[]
  voice_count: number
  voices_installed: number
  voices: TtsVoiceInfo[]
  supported: boolean
}

export type SpeechAudio = {
  samples: number[]
  sample_rate: number
}

export type DictationDownloadProgress = {
  downloaded_bytes: number
  total_bytes: number
  message?: string
}

export const VOICE_INPUT_CHANGED = 'sandwalk:voice-input-changed'
export const TTS_CHANGED = 'sandwalk:tts-changed'
export const TTS_SPEAK_PROGRESS = 'sandwalk:tts-speak-progress'

export type TtsSpeakProgress = {
  phase: string
  message: string
}

type TauriGlobal = {
  core?: { invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> }
  event?: {
    listen: (
      event: string,
      handler: (event: { payload: unknown }) => void
    ) => Promise<() => void>
  }
}

const tauri = (): TauriGlobal | null =>
  (globalThis as { __TAURI__?: TauriGlobal }).__TAURI__ ?? null

const invoke = async <T>(
  cmd: string,
  args?: Record<string, unknown>
): Promise<T | null> => {
  const api = tauri()
  if (!api?.core?.invoke) return null
  try {
    return (await api.core.invoke(cmd, args)) as T
  } catch {
    return null
  }
}

const invokeStrict = async <T>(
  cmd: string,
  args?: Record<string, unknown>
): Promise<T> => {
  const api = tauri()
  if (!api?.core?.invoke) {
    throw new Error('Voice Input is available in the Sandwalk desktop app.')
  }
  return (await api.core.invoke(cmd, args)) as T
}

export function voiceReady(status: DictationStatus | null | undefined): boolean {
  return Boolean(
    status?.supported && status.model_verified && status.test_passed
  )
}

export function voiceTtsReady(
  status: TtsStatus | null | undefined
): status is TtsStatus {
  return Boolean(status?.supported && status.model_verified)
}

export function appendTranscript(draft: string, transcript: string): string {
  const next = transcript.trim()
  if (!next) return draft
  const current = draft.trimEnd()
  return current ? `${current} ${next}` : next
}

export function publishVoiceInputChanged(status: DictationStatus) {
  window.dispatchEvent(
    new CustomEvent(VOICE_INPUT_CHANGED, { detail: status })
  )
}

export function publishTtsChanged(status: TtsStatus) {
  window.dispatchEvent(new CustomEvent(TTS_CHANGED, { detail: status }))
}

export const getDictationStatus = () =>
  invoke<DictationStatus>('get_dictation_status')

export const getDictationLevel = () => invoke<number>('dictation_level')

export const startDictation = () =>
  invokeStrict<DictationStatus>('start_dictation')

export const stopDictation = () => invokeStrict<string>('stop_dictation')

export const cancelDictation = () => invokeStrict<void>('cancel_dictation')

export const downloadDictationModel = () =>
  invokeStrict<DictationStatus>('download_dictation_model')

export const cancelDictationModelDownload = () =>
  invokeStrict<void>('cancel_dictation_model_download')

export const verifyDictationModel = () =>
  invokeStrict<DictationStatus>('verify_dictation_model')

export const markDictationTestPassed = () =>
  invokeStrict<DictationStatus>('mark_dictation_test_passed')

export const deleteDictationModel = () =>
  invokeStrict<DictationStatus>('delete_dictation_model')

export const setActiveDictationModel = () =>
  invokeStrict<DictationStatus>('set_active_dictation_model')

export const getTtsStatus = () => invoke<TtsStatus>('get_tts_status')

export const downloadTtsModel = (modelId = 'fp32') =>
  invokeStrict<TtsStatus>('download_tts_model', { modelId })

export const cancelTtsModelDownload = () =>
  invokeStrict<void>('cancel_tts_model_download')

export const verifyTtsModel = () => invokeStrict<TtsStatus>('verify_tts_model')

export const deleteTtsModel = (modelId?: string) =>
  invokeStrict<TtsStatus>(
    'delete_tts_model',
    modelId ? { modelId } : undefined
  )

export const setActiveTtsModel = (modelId: string) =>
  invokeStrict<TtsStatus>('set_active_tts_model', { modelId })

export const cancelTts = () => invokeStrict<void>('cancel_tts')

export const speakTts = (text: string, voice?: string, speed?: number) =>
  invokeStrict<SpeechAudio>('speak_tts', { text, voice, speed })

export async function listenDictationDownloadProgress(
  handler: (progress: DictationDownloadProgress) => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('dictation-download-progress', event => {
    handler(event.payload as DictationDownloadProgress)
  })
}

export async function listenTtsDownloadProgress(
  handler: (progress: DictationDownloadProgress) => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('tts-download-progress', event => {
    handler(event.payload as DictationDownloadProgress)
  })
}

export async function listenTtsSpeakProgress(
  handler: (progress: TtsSpeakProgress) => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('tts-speak-progress', event => {
    const next = event.payload as TtsSpeakProgress
    handler(next)
    window.dispatchEvent(new CustomEvent(TTS_SPEAK_PROGRESS, { detail: next }))
  })
}

let playback: {
  ctx: AudioContext
  source: AudioBufferSourceNode
  finish: () => void
} | null = null

export function stopTtsPlayback() {
  const current = playback
  playback = null
  try {
    current?.source.stop()
  } catch {
    // Already stopped.
  }
  void current?.ctx.close()
  current?.finish()
}

export async function playTtsAudio(audio: SpeechAudio): Promise<void> {
  stopTtsPlayback()
  if (!audio.samples.length) return
  const ctx = new AudioContext({ sampleRate: audio.sample_rate })
  if (ctx.state === 'suspended') {
    await ctx.resume().catch(() => undefined)
  }
  const buffer = ctx.createBuffer(1, audio.samples.length, audio.sample_rate)
  buffer.copyToChannel(Float32Array.from(audio.samples), 0)
  const source = ctx.createBufferSource()
  source.buffer = buffer
  source.connect(ctx.destination)
  const durationMs = Math.ceil((audio.samples.length / audio.sample_rate) * 1000) + 400
  await new Promise<void>((resolve, reject) => {
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      if (playback?.source === source) {
        playback = null
        void ctx.close()
      }
      resolve()
    }
    const timer = window.setTimeout(finish, durationMs)
    playback = { ctx, source, finish }
    source.onended = finish
    try {
      source.start()
    } catch (error) {
      window.clearTimeout(timer)
      if (playback?.source === source) {
        playback = null
        void ctx.close()
      }
      if (!settled) {
        settled = true
        reject(error)
      }
    }
  })
}

/** Browser-safe unsupported status when not in Tauri. */
export function browserDictationStatus(): DictationStatus {
  return {
    recording: false,
    model_installed: false,
    model_verified: false,
    test_passed: false,
    download_in_progress: false,
    model_name: 'Whisper Base Multilingual (local)',
    model_bytes: 147_951_465,
    active_model: 'multi',
    models: [],
    supported: false,
    device_summary: 'Browser',
    compatibility_reason: isTauri()
      ? null
      : 'Voice Input is available in the Sandwalk desktop app.'
  }
}

export function browserTtsStatus(): TtsStatus {
  return {
    model_installed: false,
    model_verified: false,
    download_in_progress: false,
    model_name: 'Kokoro 82M · Best',
    model_bytes: 325_532_232,
    active_model: 'fp32',
    models: [],
    voice_count: 0,
    voices_installed: 0,
    voices: [],
    supported: false
  }
}
