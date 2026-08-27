import { useEffect, useRef, useState } from 'react'

import {
  cancelTts,
  getTtsStatus,
  listenTtsSpeakProgress,
  playTtsAudio,
  speakTts,
  stopTtsPlayback,
  VOICE_INPUT_CHANGED,
  type DictationStatus,
  voiceTtsReady
} from '@/lib/desktop-voice'
import { cleanSpeechText } from '@/lib/speakable-text'
import {
  detectSpeechLanguage,
  pickCapyVoice,
  readCapyVoiceAuto,
  readCapyVoiceSpeed,
  voiceForDetectedText
} from '@/lib/capy-voice'

export function useCapyVoiceReply({
  enabled,
  liveDelta,
  replyText = '',
  runActive,
  speakTurn,
  recording
}: {
  enabled: boolean
  liveDelta: string
  replyText?: string
  runActive: boolean
  speakTurn: boolean
  recording: boolean
}) {
  const spokenRef = useRef(false)
  const turnRef = useRef(false)
  const speakingRef = useRef(false)
  const lastDeltaRef = useRef('')
  const [speakStatus, setSpeakStatus] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let stop = () => {}
    void listenTtsSpeakProgress(next => {
      if (!active) return
      if (!turnRef.current && !speakingRef.current) return
      if (next.phase === 'spoke') return
      setSpeakStatus(next.message)
    }).then(unlisten => {
      stop = unlisten
    })
    return () => {
      active = false
      stop()
      setSpeakStatus(null)
    }
  }, [])

  useEffect(() => {
    const stop = () => {
      stopTtsPlayback()
      void cancelTts().catch(() => undefined)
    }
    if (recording) {
      stop()
      setSpeakStatus(null)
    }
    const onVoice = (event: Event) => {
      const status = (event as CustomEvent<DictationStatus>).detail
      if (status?.recording) {
        stop()
        setSpeakStatus(null)
      }
    }
    window.addEventListener(VOICE_INPUT_CHANGED, onVoice)
    return () => window.removeEventListener(VOICE_INPUT_CHANGED, onVoice)
  }, [recording])

  useEffect(() => {
    if (liveDelta) lastDeltaRef.current = liveDelta
  }, [liveDelta])

  useEffect(() => {
    if (runActive && speakTurn) {
      turnRef.current = true
      spokenRef.current = false
    }
    if (!speakTurn && !runActive) {
      turnRef.current = false
    }
  }, [runActive, speakTurn])

  useEffect(() => {
    if (!enabled || !speakTurn || runActive || recording) return
    if (!turnRef.current || spokenRef.current || speakingRef.current) return
    const source = liveDelta || lastDeltaRef.current || replyText
    const lang = detectSpeechLanguage(source)
    const text = cleanSpeechText(source, lang)
    if (!text) {
      spokenRef.current = true
      turnRef.current = false
      return
    }
    speakingRef.current = true
    spokenRef.current = true
    setSpeakStatus('Loading model into memory…')
    void (async () => {
      try {
        const status = await getTtsStatus()
        if (!voiceTtsReady(status)) return
        const selected = pickCapyVoice(status.voices, status.active_model)
        const voice = readCapyVoiceAuto()
          ? voiceForDetectedText(source, selected, status.voices)
          : selected
        const audio = await speakTts(text, voice, readCapyVoiceSpeed())
        setSpeakStatus('Playing…')
        await playTtsAudio(audio)
      } catch {
        // Stay silent if TTS is missing or the user barged in.
      } finally {
        speakingRef.current = false
        setSpeakStatus(null)
        turnRef.current = false
      }
    })()
  }, [enabled, liveDelta, recording, replyText, runActive, speakTurn])

  return { speakStatus }
}
