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

export type TtsStatus = {
  model_installed: boolean
  model_verified: boolean
  download_in_progress: boolean
  model_name: string
  model_bytes: number
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
}

export const VOICE_INPUT_CHANGED = 'sandwalk:voice-input-changed'
export const TTS_CHANGED = 'sandwalk:tts-changed'

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

export function voiceTtsReady(status: TtsStatus | null | undefined): boolean {
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

export const downloadDictationModel = (modelId = 'en') =>
  invokeStrict<DictationStatus>('download_dictation_model', {
    model_id: modelId
  })

export const cancelDictationModelDownload = () =>
  invokeStrict<void>('cancel_dictation_model_download')

export const verifyDictationModel = (modelId?: string) =>
  invokeStrict<DictationStatus>(
    'verify_dictation_model',
    modelId ? { model_id: modelId } : undefined
  )

export const markDictationTestPassed = () =>
  invokeStrict<DictationStatus>('mark_dictation_test_passed')

export const deleteDictationModel = (modelId?: string) =>
  invokeStrict<DictationStatus>(
    'delete_dictation_model',
    modelId ? { model_id: modelId } : undefined
  )

export const setActiveDictationModel = (modelId: string) =>
  invokeStrict<DictationStatus>('set_active_dictation_model', {
    model_id: modelId
  })

export const getTtsStatus = () => invoke<TtsStatus>('get_tts_status')

export const downloadTtsModel = () => invokeStrict<TtsStatus>('download_tts_model')

export const cancelTtsModelDownload = () =>
  invokeStrict<void>('cancel_tts_model_download')

export const verifyTtsModel = () => invokeStrict<TtsStatus>('verify_tts_model')

export const deleteTtsModel = () => invokeStrict<TtsStatus>('delete_tts_model')

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

let playback: { ctx: AudioContext; source: AudioBufferSourceNode } | null =
  null

export function stopTtsPlayback() {
  playback?.source.stop()
  void playback?.ctx.close()
  playback = null
}

export async function playTtsAudio(audio: SpeechAudio): Promise<void> {
  stopTtsPlayback()
  if (!audio.samples.length) return
  const ctx = new AudioContext({ sampleRate: audio.sample_rate })
  const buffer = ctx.createBuffer(1, audio.samples.length, audio.sample_rate)
  buffer.copyToChannel(Float32Array.from(audio.samples), 0)
  const source = ctx.createBufferSource()
  source.buffer = buffer
  source.connect(ctx.destination)
  playback = { ctx, source }
  await new Promise<void>((resolve, reject) => {
    source.onended = () => {
      if (playback?.source === source) {
        void ctx.close()
        playback = null
      }
      resolve()
    }
    try {
      source.start()
    } catch (error) {
      reject(error)
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
    model_name: 'Whisper Base English (local)',
    model_bytes: 147_964_211,
    active_model: 'en',
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
    model_name: 'Kokoro 82M (local)',
    model_bytes: 86_033_585,
    voice_count: 0,
    voices_installed: 0,
    voices: [],
    supported: false
  }
}
