import { useEffect, useRef } from 'react'

import {
  cancelTts,
  getTtsStatus,
  playTtsAudio,
  speakTts,
  stopTtsPlayback,
  VOICE_INPUT_CHANGED,
  type DictationStatus,
  voiceTtsReady
} from '@/lib/desktop-voice'
import {
  completedSentences,
  speakableText,
  splitSentences
} from '@/lib/speakable-text'
import { readCapyVoice, readCapyVoiceSpeed } from '@/lib/capy-voice'

export function useCapyVoiceReply({
  enabled,
  liveDelta,
  runActive,
  speakTurn,
  recording
}: {
  enabled: boolean
  liveDelta: string
  runActive: boolean
  speakTurn: boolean
  recording: boolean
}) {
  const spokenRef = useRef(0)
  const turnRef = useRef(false)
  const speakingRef = useRef(false)
  const lastDeltaRef = useRef('')

  useEffect(() => {
    const stop = () => {
      stopTtsPlayback()
      void cancelTts().catch(() => undefined)
    }
    if (recording) stop()
    const onVoice = (event: Event) => {
      const status = (event as CustomEvent<DictationStatus>).detail
      if (status?.recording) stop()
    }
    window.addEventListener(VOICE_INPUT_CHANGED, onVoice)
    return () => window.removeEventListener(VOICE_INPUT_CHANGED, onVoice)
  }, [recording])

  useEffect(() => {
    if (runActive && speakTurn) {
      turnRef.current = true
      spokenRef.current = 0
    }
    if (!runActive && !speakTurn) {
      turnRef.current = false
    }
  }, [runActive, speakTurn])

  useEffect(() => {
    if (!enabled || !turnRef.current || recording || speakingRef.current) return
    if (liveDelta) lastDeltaRef.current = liveDelta
    const source = liveDelta || lastDeltaRef.current
    const readySentences = runActive
      ? completedSentences(source)
      : splitSentences(source)
    const pending = readySentences.slice(spokenRef.current, 2)
    if (!pending.length) return
    const text = speakableText(pending.join(' '), pending.length)
    if (!text) {
      spokenRef.current += pending.length
      return
    }
    speakingRef.current = true
    void (async () => {
      try {
        const status = await getTtsStatus()
        if (!voiceTtsReady(status)) return
        const audio = await speakTts(
          text,
          readCapyVoice(),
          readCapyVoiceSpeed()
        )
        await playTtsAudio(audio)
        spokenRef.current += pending.length
      } catch {
        // Stay silent if TTS is missing or the user barged in.
      } finally {
        speakingRef.current = false
        if (!runActive) turnRef.current = false
      }
    })()
  }, [enabled, liveDelta, recording, runActive])
}
