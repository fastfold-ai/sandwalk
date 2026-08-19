import { useCallback, useEffect, useRef, useState } from 'react'

import { isTauri } from '@/lib/desktop'
import {
  cancelDictation,
  getDictationStatus,
  startDictation,
  stopDictation,
  voiceReady
} from '@/lib/desktop-voice'
import { createDoubleTap, isCapyHandsFreeKey } from '@/lib/capy-ui'

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
  const recordingRef = useRef(false)
  const transcribingRef = useRef(false)
  const runActiveRef = useRef(runActive)
  const sendRef = useRef(send)
  recordingRef.current = recording
  transcribingRef.current = transcribing
  runActiveRef.current = runActive
  sendRef.current = send

  const cancel = useCallback(async () => {
    await cancelDictation().catch(() => undefined)
    recordingRef.current = false
    transcribingRef.current = false
    setRecording(false)
    setTranscribing(false)
  }, [])

  const toggle = useCallback(async () => {
    if (!desktop || transcribingRef.current || runActiveRef.current) return
    if (recordingRef.current) {
      transcribingRef.current = true
      setTranscribing(true)
      setRecording(false)
      recordingRef.current = false
      try {
        const transcript = (await stopDictation()).trim()
        if (transcript) await sendRef.current(transcript)
      } catch {
        await cancelDictation().catch(() => undefined)
      } finally {
        transcribingRef.current = false
        setTranscribing(false)
      }
      return
    }
    const status = await getDictationStatus()
    if (!voiceReady(status)) return
    try {
      const next = await startDictation()
      if (!next?.recording) return
      recordingRef.current = true
      setRecording(true)
    } catch {
      recordingRef.current = false
      setRecording(false)
    }
  }, [desktop])

  useEffect(() => {
    if (!enabled || !desktop) return
    const tapped = createDoubleTap()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && recordingRef.current) {
        event.preventDefault()
        void cancel()
        return
      }
      if (!isCapyHandsFreeKey(event)) return
      if (!tapped()) return
      event.preventDefault()
      void toggle()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [cancel, desktop, enabled, toggle])

  useEffect(() => {
    if (enabled) return
    if (recordingRef.current) void cancel()
  }, [cancel, enabled])

  return { recording, transcribing }
}
