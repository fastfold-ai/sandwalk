import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { isTauri } from '@/lib/desktop'
import {
  appendTranscript,
  cancelDictation,
  type DictationStatus,
  getDictationLevel,
  getDictationStatus,
  startDictation,
  stopDictation,
  publishVoiceInputChanged,
  VOICE_INPUT_CHANGED,
  voiceReady
} from '@/lib/desktop-voice'

export function useComposerVoice({
  draft,
  commitDraft,
  focusInput
}: {
  draft: string
  commitDraft: (value: string) => void
  focusInput: () => void
}) {
  const navigate = useNavigate()
  const desktop = isTauri()
  const [dictation, setDictation] = useState<DictationStatus | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const [levels, setLevels] = useState<number[]>([])
  const [fromVoice, setFromVoice] = useState(false)

  useEffect(() => {
    if (!desktop) return
    const refresh = (event?: Event) => {
      const supplied = (event as CustomEvent<DictationStatus> | undefined)
        ?.detail
      if (supplied) {
        setDictation(supplied)
        return
      }
      void getDictationStatus().then(status => {
        if (status) setDictation(status)
      })
    }
    refresh()
    window.addEventListener(VOICE_INPUT_CHANGED, refresh)
    return () => window.removeEventListener(VOICE_INPUT_CHANGED, refresh)
  }, [desktop])

  useEffect(() => {
    if (!dictation?.recording) {
      setRecordingSeconds(0)
      return
    }
    const started = Date.now()
    const timer = window.setInterval(() => {
      setRecordingSeconds(Math.floor((Date.now() - started) / 1000))
    }, 250)
    return () => window.clearInterval(timer)
  }, [dictation?.recording])

  useEffect(() => {
    if (!dictation?.recording) {
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
  }, [dictation?.recording])

  const cancel = useCallback(async () => {
    setError(null)
    setBusy(null)
    await cancelDictation().catch(() => undefined)
    const status = await getDictationStatus()
    if (status) setDictation(status)
  }, [])

  useEffect(() => {
    if (!dictation?.recording) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      void cancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cancel, dictation?.recording])

  const ready = voiceReady(dictation)
  const recording = Boolean(dictation?.recording)
  const transcribing = busy === 'Transcribing…'
  const active = recording || transcribing
  const recordingTime = `${Math.floor(recordingSeconds / 60)}:${String(
    recordingSeconds % 60
  ).padStart(2, '0')}`

  const toggle = async () => {
    if (!desktop || busy) return
    setError(null)
    try {
      if (recording) {
        setBusy('Transcribing…')
        const transcript = await stopDictation()
        if (transcript === null) {
          throw new Error('Could not transcribe your recording.')
        }
        if (transcript.trim()) {
          commitDraft(appendTranscript(draft, transcript))
          setFromVoice(true)
        }
        const status = await getDictationStatus()
        if (status) setDictation(status)
        focusInput()
        return
      }

      const status = dictation || (await getDictationStatus())
      if (!status) throw new Error('Voice dictation is unavailable.')
      if (!voiceReady(status)) {
        navigate('/dashboard/voice')
        return
      }
      setBusy('Starting microphone…')
      const next = await startDictation()
      if (!next?.recording) {
        throw new Error('Could not start the microphone.')
      }
      publishVoiceInputChanged(next)
      setDictation(next)
    } catch (voiceError) {
      setError(
        voiceError instanceof Error
          ? voiceError.message
          : 'Voice dictation is unavailable.'
      )
      const status = await getDictationStatus()
      if (status) setDictation(status)
    } finally {
      setBusy(null)
    }
  }

  return {
    showMic: desktop,
    ready,
    recording,
    transcribing,
    active,
    busy,
    error,
    levels,
    recordingTime,
    fromVoice,
    clearFromVoice: () => setFromVoice(false),
    toggle,
    cancel
  }
}
