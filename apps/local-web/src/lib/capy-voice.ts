export const CAPY_SPEAK_ALL_KEY = 'sandwalk:capy-speak-all'
export const CAPY_VOICE_KEY = 'sandwalk:capy-voice'
export const CAPY_VOICE_BY_ENGINE_KEY = 'sandwalk:capy-voice-by-engine'
export const CAPY_VOICE_SPEED_KEY = 'sandwalk:capy-voice-speed'
export const CAPY_VOICE_AUTO_KEY = 'sandwalk:capy-voice-auto'
export const DEFAULT_CAPY_VOICE = 'af_heart'
export const DEFAULT_CAPY_VOICE_SPEED = 2

const LANGUAGE_NAME_BY_CODE: Record<string, string> = {
  en: 'English',
  es: 'Spanish',
  fr: 'French',
  de: 'German',
  it: 'Italian',
  pt: 'Portuguese',
  zh: 'Chinese',
  ja: 'Japanese',
  ko: 'Korean',
  hi: 'Hindi',
  ar: 'Arabic',
  nl: 'Dutch',
  pl: 'Polish',
  ru: 'Russian',
  tr: 'Turkish',
  sv: 'Swedish',
  da: 'Danish',
  fi: 'Finnish',
  no: 'Norwegian',
  el: 'Greek',
  he: 'Hebrew',
  ms: 'Malay',
  sw: 'Swahili'
}

type VoiceChoice = { id: string; language_code: string }

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

function readVoiceByEngine(): Record<string, string> {
  try {
    const raw = window.localStorage.getItem(CAPY_VOICE_BY_ENGINE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    const next: Record<string, string> = {}
    for (const [engine, voice] of Object.entries(parsed)) {
      if (typeof voice === 'string' && voice) next[engine] = voice
    }
    return next
  } catch {
    return {}
  }
}

export function readCapyVoice(): string {
  return window.localStorage.getItem(CAPY_VOICE_KEY) || DEFAULT_CAPY_VOICE
}

export function writeCapyVoice(voice: string, engine?: string) {
  window.localStorage.setItem(CAPY_VOICE_KEY, voice)
  if (!engine) return
  const map = readVoiceByEngine()
  map[engine] = voice
  window.localStorage.setItem(CAPY_VOICE_BY_ENGINE_KEY, JSON.stringify(map))
}

export function resolveCapyVoice(stored: string, voices: VoiceChoice[]): string {
  if (!voices.length) return stored || DEFAULT_CAPY_VOICE
  if (voices.some(voice => voice.id === stored)) return stored
  const language = languageCodeFromVoice(stored)
  return (
    voices.find(voice => voice.language_code === language)?.id || voices[0].id
  )
}

export function pickCapyVoice(voices: VoiceChoice[], engine?: string): string {
  const stored =
    (engine && readVoiceByEngine()[engine]) || readCapyVoice()
  return resolveCapyVoice(stored, voices)
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
  return window.localStorage.getItem(CAPY_VOICE_AUTO_KEY) === '1'
}

export function writeCapyVoiceAuto(value: boolean) {
  window.localStorage.setItem(CAPY_VOICE_AUTO_KEY, value ? '1' : '0')
}

export function languageCodeFromVoice(voiceId: string): string {
  if (voiceId.startsWith('cb_')) return voiceId.slice(3) || 'en'
  if (voiceId.startsWith('qwen_')) {
    if (voiceId === 'qwen_Ryan' || voiceId === 'qwen_Aiden') return 'en'
    if (voiceId === 'qwen_Ono_Anna') return 'ja'
    if (voiceId === 'qwen_Sohee') return 'ko'
    return 'zh'
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
  let hangul = 0
  let devanagari = 0
  for (const char of text) {
    const code = char.codePointAt(0) || 0
    if (code >= 0x3040 && code <= 0x30ff) kana += 1
    else if (code >= 0xac00 && code <= 0xd7af) hangul += 1
    else if (code >= 0x4e00 && code <= 0x9fff) han += 1
    else if (code >= 0x0900 && code <= 0x097f) devanagari += 1
  }
  if (kana > 0) return 'ja'
  if (hangul > 1) return 'ko'
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

export function languageNameFromCode(languageCode: string): string {
  return LANGUAGE_NAME_BY_CODE[languageCode] || 'English'
}

export function languageForVoice(
  voiceId: string,
  voices: Array<{ id: string; language: string }>
): string {
  return (
    voices.find(voice => voice.id === voiceId)?.language ||
    languageNameFromCode(languageCodeFromVoice(voiceId))
  )
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
    case 'ko':
      return '안녕하세요, 캐피예요. 채팅을 열고 짧게 답할 수 있어요.'
    case 'zh':
      return '你好，我是 Capy。我可以开新对话，并短短回答你。'
    default:
      return "Hi, I'm Capy. I can start chats, run Doctor, and keep replies short."
  }
}
