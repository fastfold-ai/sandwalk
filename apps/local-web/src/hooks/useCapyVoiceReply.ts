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
import {
  completedSentences,
  speakableBudget,
  speakableText,
  splitSentences
} from '@/lib/speakable-text'
import {
  detectSpeechLanguage,
  readCapyVoice,
  readCapyVoiceAuto,
  readCapyVoiceSpeed,
  voiceForDetectedText
} from '@/lib/capy-voice'

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
  const [speakStatus, setSpeakStatus] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let stop = () => {}
    void listenTtsSpeakProgress(next => {
      if (!active || next.phase === 'spoke') return
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
    const lang = detectSpeechLanguage(source)
    const budget = speakableBudget(lang)
    const pending = readySentences.slice(spokenRef.current, budget.sentences)
    if (!pending.length) return
    const raw = pending.join(lang === 'zh' || lang === 'ja' ? '' : ' ')
    const text = speakableText(raw, budget.sentences, budget.chars, lang)
    if (!text) {
      spokenRef.current += pending.length
      return
    }
    speakingRef.current = true
    setSpeakStatus('Loading model into memory…')
    void (async () => {
      try {
        const status = await getTtsStatus()
        if (!voiceTtsReady(status)) return
        const voice = readCapyVoiceAuto()
          ? voiceForDetectedText(raw, readCapyVoice(), status.voices)
          : readCapyVoice()
        const audio = await speakTts(text, voice, readCapyVoiceSpeed())
        setSpeakStatus('Playing…')
        await playTtsAudio(audio)
        spokenRef.current += pending.length
      } catch {
        // Stay silent if TTS is missing or the user barged in.
      } finally {
        speakingRef.current = false
        setSpeakStatus(null)
        if (!runActive) turnRef.current = false
      }
    })()
  }, [enabled, liveDelta, recording, runActive])

  return { speakStatus }
}
