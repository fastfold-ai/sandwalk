export const CAPY_SPEAK_ALL_KEY = 'sandwalk:capy-speak-all'
export const CAPY_VOICE_KEY = 'sandwalk:capy-voice'
export const CAPY_VOICE_SPEED_KEY = 'sandwalk:capy-voice-speed'
export const CAPY_VOICE_AUTO_KEY = 'sandwalk:capy-voice-auto'
export const DEFAULT_CAPY_VOICE = 'af_heart'
export const DEFAULT_CAPY_VOICE_SPEED = 1

export const DEFAULT_VOICE_BY_LANGUAGE: Record<string, string> = {
  en: 'af_heart',
  es: 'ef_dora',
  fr: 'ff_siwis',
  hi: 'hf_alpha',
  it: 'if_sara',
  pt: 'pf_dora',
  ja: 'jf_alpha',
  zh: 'zf_xiaoxiao'
}

export function readCapySpeakAll(): boolean {
  return window.localStorage.getItem(CAPY_SPEAK_ALL_KEY) === '1'
}

export function writeCapySpeakAll(value: boolean) {
  window.localStorage.setItem(CAPY_SPEAK_ALL_KEY, value ? '1' : '0')
}

export function readCapyVoice(): string {
  return window.localStorage.getItem(CAPY_VOICE_KEY) || DEFAULT_CAPY_VOICE
}

export function writeCapyVoice(voice: string) {
  window.localStorage.setItem(CAPY_VOICE_KEY, voice)
}

export function readCapyVoiceSpeed(): number {
  const stored = window.localStorage.getItem(CAPY_VOICE_SPEED_KEY)
  if (stored == null || stored === '') return DEFAULT_CAPY_VOICE_SPEED
  const raw = Number(stored)
  if (!Number.isFinite(raw)) return DEFAULT_CAPY_VOICE_SPEED
  return Math.min(2, Math.max(0.5, raw))
}

export function writeCapyVoiceSpeed(speed: number) {
  window.localStorage.setItem(CAPY_VOICE_SPEED_KEY, String(speed))
}

export function readCapyVoiceAuto(): boolean {
  return window.localStorage.getItem(CAPY_VOICE_AUTO_KEY) !== '0'
}

export function writeCapyVoiceAuto(value: boolean) {
  window.localStorage.setItem(CAPY_VOICE_AUTO_KEY, value ? '1' : '0')
}

export function languageCodeFromVoice(voiceId: string): string {
  if (voiceId.startsWith('cb_')) return voiceId.slice(3) || 'en'
  if (voiceId.startsWith('qwen_')) {
    return voiceId === 'qwen_Ryan' || voiceId === 'qwen_Aiden' ? 'en' : 'zh'
  }
  switch (voiceId.charAt(0)) {
    case 'e':
      return 'es'
    case 'f':
      return 'fr'
    case 'h':
      return 'hi'
    case 'i':
      return 'it'
    case 'j':
      return 'ja'
    case 'p':
      return 'pt'
    case 'z':
      return 'zh'
    default:
      return 'en'
  }
}

export function defaultVoiceForLanguage(languageCode: string): string {
  return DEFAULT_VOICE_BY_LANGUAGE[languageCode] || DEFAULT_CAPY_VOICE
}

export function detectSpeechLanguage(text: string): string {
  let han = 0
  let kana = 0
  let devanagari = 0
  for (const char of text) {
    const code = char.codePointAt(0) || 0
    if (code >= 0x3040 && code <= 0x30ff) kana += 1
    else if (code >= 0x4e00 && code <= 0x9fff) han += 1
    else if (code >= 0x0900 && code <= 0x097f) devanagari += 1
  }
  if (kana > 0) return 'ja'
  if (devanagari > 1) return 'hi'
  if (han > 1) return 'zh'
  const lower = text.toLowerCase()
  if (/\b(hola|soy|qué|gracias|puedo|estoy)\b/.test(lower)) return 'es'
  if (/\b(bonjour|je suis|merci|peux)\b/.test(lower)) return 'fr'
  if (/\b(ciao|sono|grazie|posso)\b/.test(lower)) return 'it'
  if (/\b(olá|ola|sou|obrigad|posso)\b/.test(lower)) return 'pt'
  return 'en'
}

export function voiceForDetectedText(
  text: string,
  currentVoice: string,
  voices?: Array<{ id: string; language_code: string }>
): string {
  const language = detectSpeechLanguage(text)
  if (voices?.length) {
    if (
      voices.find(voice => voice.id === currentVoice)?.language_code ===
      language
    ) {
      return currentVoice
    }
    return (
      voices.find(voice => voice.language_code === language)?.id ||
      currentVoice
    )
  }
  if (languageCodeFromVoice(currentVoice) === language) return currentVoice
  return defaultVoiceForLanguage(language)
}

export function languageForVoice(
  voiceId: string,
  voices: Array<{ id: string; language: string }>
): string {
  return voices.find(voice => voice.id === voiceId)?.language || 'English'
}

export function shouldSpeakCapyReply(voiceTurn: boolean, speakAll: boolean) {
  return voiceTurn || speakAll
}

export function previewPhrase(languageCode: string): string {
  switch (languageCode) {
    case 'es':
      return 'Hola, soy Capy. Puedo abrir chats, correr Doctor y responder corto.'
    case 'fr':
      return 'Bonjour, je suis Capy. Je peux ouvrir des chats, lancer Doctor et rester bref.'
    case 'hi':
      return 'नमस्ते, मैं कैपी हूँ। मैं चैट शुरू कर सकता हूँ और छोटे जवाब दे सकता हूँ।'
    case 'it':
      return 'Ciao, sono Capy. Posso aprire chat, avviare Doctor e rispondere in breve.'
    case 'pt':
      return 'Olá, eu sou o Capy. Posso abrir chats, rodar o Doctor e responder curto.'
    case 'ja':
      return 'こんにちは、キャピーです。チャットを始めて、短く返事できます。'
    case 'zh':
      return '你好，我是 Capy。我可以开新对话，并短短回答你。'
    default:
      return "Hi, I'm Capy. I can start chats, run Doctor, and keep replies short."
  }
}
