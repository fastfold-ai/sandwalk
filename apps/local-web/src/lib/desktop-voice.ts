/**
 * Local dictation bridge (desktop Tauri only). Browser builds soft-fail —
 * Voice Input stays unavailable rather than sending mic audio to a server.
 */

import { isTauri } from '@/lib/desktop'

export type DictationStatus = {
  recording: boolean
  model_installed: boolean
  model_verified: boolean
  test_passed: boolean
  download_in_progress: boolean
  model_name: string
  model_bytes: number
  supported: boolean
  device_summary: string
  compatibility_reason: string | null
}

export type DictationDownloadProgress = {
  downloaded_bytes: number
  total_bytes: number
}

export const VOICE_INPUT_CHANGED = 'sandwalk:voice-input-changed'

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

export async function listenDictationDownloadProgress(
  handler: (progress: DictationDownloadProgress) => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('dictation-download-progress', event => {
    handler(event.payload as DictationDownloadProgress)
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
    supported: false,
    device_summary: 'Browser',
    compatibility_reason: isTauri()
      ? null
      : 'Voice Input is available in the Sandwalk desktop app.'
  }
}
