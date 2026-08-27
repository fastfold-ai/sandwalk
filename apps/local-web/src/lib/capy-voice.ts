export const CAPY_SPEAK_ALL_KEY = 'sandwalk:capy-speak-all'
export const CAPY_VOICE_KEY = 'sandwalk:capy-voice'
export const CAPY_VOICE_SPEED_KEY = 'sandwalk:capy-voice-speed'
export const DEFAULT_CAPY_VOICE = 'af_heart'
export const DEFAULT_CAPY_VOICE_SPEED = 1

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
  const raw = Number(window.localStorage.getItem(CAPY_VOICE_SPEED_KEY))
  if (!Number.isFinite(raw)) return DEFAULT_CAPY_VOICE_SPEED
  return Math.min(2, Math.max(0.5, raw))
}

export function writeCapyVoiceSpeed(speed: number) {
  window.localStorage.setItem(CAPY_VOICE_SPEED_KEY, String(speed))
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
      return 'Hola, soy Capy.'
    case 'fr':
      return 'Bonjour, je suis Capy.'
    case 'hi':
      return 'नमस्ते, मैं कैपी हूँ।'
    case 'it':
      return 'Ciao, sono Capy.'
    case 'pt':
      return 'Olá, eu sou o Capy.'
    case 'ja':
      return 'こんにちは、キャピーです。'
    case 'zh':
      return '你好，我是 Capy。'
    default:
      return 'Hi, I am Capy.'
  }
}
