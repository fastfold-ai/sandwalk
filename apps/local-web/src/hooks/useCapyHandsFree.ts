import { useCallback, useEffect, useRef, useState } from 'react'

import {
  isCapyHandsFreeKey,
  requestRevealCapyMinimized
} from '@/lib/capy-ui'
import { isTauri } from '@/lib/desktop'
import {
  cancelDictation,
  getDictationLevel,
  getDictationStatus,
  publishVoiceInputChanged,
  startDictation,
  stopDictation,
  usableVoiceTranscript,
  voiceReady
} from '@/lib/desktop-voice'

export function useCapyHandsFree({
  enabled,
  send,
  runActive
}: {
  enabled: boolean
  send: (text: string) => void | Promise<void>
  runActive: boolean
}) {
  const desktop = isTauri()
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [levels, setLevels] = useState<number[]>([])
  const recordingRef = useRef(false)
  const transcribingRef = useRef(false)
  const inFlightRef = useRef(false)
  const runActiveRef = useRef(runActive)
  const sendRef = useRef(send)
  recordingRef.current = recording
  transcribingRef.current = transcribing
  runActiveRef.current = runActive
  sendRef.current = send

  const publishCapyStatus = async (nextRecording: boolean) => {
    const status = await getDictationStatus()
    if (status) publishVoiceInputChanged({ ...status, recording: nextRecording }, 'capy')
  }

  const clearListening = useCallback(async () => {
    recordingRef.current = false
    transcribingRef.current = false
    setRecording(false)
    setTranscribing(false)
    setLevels([])
    await publishCapyStatus(false)
  }, [])

  const cancel = useCallback(async () => {
    await cancelDictation().catch(() => undefined)
    await clearListening()
  }, [clearListening])

  const toggle = useCallback(async () => {
    if (!desktop || transcribingRef.current || inFlightRef.current) return
    inFlightRef.current = true
    try {
      if (recordingRef.current) {
        transcribingRef.current = true
        setTranscribing(true)
        recordingRef.current = false
        setRecording(false)
        setLevels([])
        try {
          const transcript = usableVoiceTranscript(await stopDictation())
          await publishCapyStatus(false)
          if (transcript) await sendRef.current(transcript)
        } catch {
          await cancelDictation().catch(() => undefined)
          await publishCapyStatus(false)
        } finally {
          transcribingRef.current = false
          setTranscribing(false)
        }
        return
      }

      const status = await getDictationStatus()
      if (!voiceReady(status)) return
      try {
        await cancelDictation().catch(() => undefined)
        const next = await startDictation()
        const live = next?.recording
          ? next
          : (await getDictationStatus().catch(() => null))
        if (!live?.recording) {
          await clearListening()
          return
        }
        publishVoiceInputChanged(live, 'capy')
        recordingRef.current = true
        setRecording(true)
      } catch {
        const live = await getDictationStatus().catch(() => null)
        if (live?.recording) {
          publishVoiceInputChanged(live, 'capy')
          recordingRef.current = true
          setRecording(true)
          return
        }
        await clearListening()
      }
    } finally {
      inFlightRef.current = false
    }
  }, [clearListening, desktop])

  useEffect(() => {
    if (!enabled) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && recordingRef.current) {
        event.preventDefault()
        void cancel()
        return
      }
      if (!isCapyHandsFreeKey(event)) return
      event.preventDefault()
      event.stopPropagation()
      requestRevealCapyMinimized()
      void toggle()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [cancel, enabled, toggle])

  useEffect(() => {
    if (enabled) return
    if (recordingRef.current) void cancel()
  }, [cancel, enabled])

  useEffect(() => {
    if (!recording) return
    const timer = window.setInterval(() => {
      void getDictationStatus().then(status => {
        if (!recordingRef.current) return
        if (status && !status.recording) {
          recordingRef.current = false
          setRecording(false)
          setLevels([])
          publishVoiceInputChanged({ ...status, recording: false }, 'capy')
        }
      })
    }, 400)
    return () => window.clearInterval(timer)
  }, [recording])

  useEffect(() => {
    if (!recording) {
      setLevels([])
      return
    }
    const timer = window.setInterval(() => {
      void getDictationLevel().then(level => {
        if (!recordingRef.current || typeof level !== 'number') return
        setLevels(cur => [...cur.slice(-13), level])
      })
    }, 100)
    return () => window.clearInterval(timer)
  }, [recording])

  return { recording, transcribing, levels, toggle, cancel }
}
