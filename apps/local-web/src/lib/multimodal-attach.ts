/** Client-side multimodal attach hints (mirrors Deep Agents extension table). */

export type MultimodalKind = 'image' | 'file' | 'audio' | 'video'

const IMAGE_EXT = new Set([
  'png',
  'jpg',
  'jpeg',
  'gif',
  'webp',
  'heic',
  'heif'
])
const FILE_EXT = new Set(['pdf', 'ppt', 'pptx'])
const AUDIO_EXT = new Set(['wav', 'mp3', 'aiff', 'aac', 'ogg', 'flac'])
const VIDEO_EXT = new Set([
  'mp4',
  'mpeg',
  'mov',
  'avi',
  'flv',
  'mpg',
  'webm',
  'wmv',
  '3gpp'
])

/** Keep in sync with cli/src/agent/model_catalog/modality_support.py */
const LOCAL_IMAGE_VIDEO_MARKERS = [
  'qwen3.5',
  'qwen3-5',
  'qwen3_5',
  'qwen3.6',
  'qwen3-6',
  'qwen3_6'
] as const

const LOCAL_IMAGE_MARKERS = [
  'diffusiongemma',
  'diffusion-gemma',
  'gemma4',
  'gemma-4',
  'nemotron3',
  'nemotron-3',
  'llava',
  'bakllava',
  'moondream',
  'minicpm-v',
  'minicpmv',
  'qwen2-vl',
  'qwen2.5-vl',
  'qwen2-5-vl',
  'qwen3-vl',
  'qwen-vl',
  'llama3.2-vision',
  'llama-3.2-vision',
  'pixtral'
] as const

export function multimodalKindForFile(file: {
  name: string
  type?: string
}): MultimodalKind | null {
  const name = String(file.name || '')
  const ext = name.includes('.')
    ? name.split('.').pop()!.toLowerCase()
    : ''
  const mime = String(file.type || '').toLowerCase()
  if (IMAGE_EXT.has(ext) || mime.startsWith('image/')) return 'image'
  if (FILE_EXT.has(ext) || mime === 'application/pdf') return 'file'
  if (AUDIO_EXT.has(ext) || mime.startsWith('audio/')) return 'audio'
  if (VIDEO_EXT.has(ext) || mime.startsWith('video/')) return 'video'
  return null
}

export type MultimodalCapabilityFlags = {
  supportsImageInputs?: boolean
  supportsPdfInputs?: boolean
  supportsAudioInputs?: boolean
  supportsVideoInputs?: boolean
}

function normalizeLocalModelName(value: string): string {
  const normalized = value.trim().toLowerCase().replaceAll('_', '-').replaceAll(' ', '-')
  if (normalized.includes('/')) {
    return normalized.split('/').at(-1) || normalized
  }
  return normalized
}

function localAllowlistFlags(modelId: string): MultimodalCapabilityFlags {
  const name = normalizeLocalModelName(modelId)
  if (!name) return {}
  const base = name.split(':', 1)[0] || name
  const matches = (marker: string) =>
    name.includes(marker) || name.startsWith(marker) || base.startsWith(marker)

  if (LOCAL_IMAGE_VIDEO_MARKERS.some(matches)) {
    return { supportsImageInputs: true, supportsVideoInputs: true }
  }
  if (
    LOCAL_IMAGE_MARKERS.some(matches) ||
    name.includes('vision') ||
    name.includes('-vl') ||
    base.endsWith('-vl') ||
    base.endsWith('vl')
  ) {
    return { supportsImageInputs: true }
  }
  return {}
}

/**
 * Merge API/catalog flags with the local-family allowlist so the multimodal
 * compatibility table and composer attach hints stay consistent.
 */
export function resolveMultimodalCapabilityFlags(model: {
  provider?: string | null
  id?: string | null
  label?: string | null
  model?: string | null
  supportsImageInputs?: boolean
  supportsPdfInputs?: boolean
  supportsAudioInputs?: boolean
  supportsVideoInputs?: boolean
}): MultimodalCapabilityFlags {
  const provider = String(model.provider || '').trim().toLowerCase()
  // Match server modality_support: local VLMs remapped to openai at runtime
  // still need family-name heuristics (oMLX / Ollama / MLX).
  const inferLocalFamilies =
    provider === 'local' ||
    provider === 'compatible' ||
    provider === 'openai-compatible' ||
    provider === 'openai' ||
    provider === 'openai-chatgpt' ||
    provider === 'opencode' ||
    provider === 'nvidia' ||
    !provider
  const inferred = inferLocalFamilies
    ? {
        ...localAllowlistFlags(String(model.id || model.model || '')),
        ...localAllowlistFlags(String(model.label || ''))
      }
    : {}

  // Google Gemini (incl. gemini-4-argon, 3.x, 2.5): native Image, PDF, Audio, Video.
  const bareId = normalizeLocalModelName(String(model.id || model.model || ''))
  const isGeminiOrMuse =
    provider === 'google' ||
    provider === 'meta' ||
    bareId.startsWith('gemini-') ||
    bareId.startsWith('muse-wonder') ||
    bareId.startsWith('muse-spark') ||
    String(model.id || model.model || '').trim().toLowerCase().startsWith('google/gemini-') ||
    String(model.id || model.model || '').trim().toLowerCase().startsWith('meta/muse-')
  const geminiFlags: MultimodalCapabilityFlags = isGeminiOrMuse
    ? {
        supportsImageInputs: true,
        supportsPdfInputs: true,
        supportsAudioInputs: true,
        supportsVideoInputs: true
      }
    : {}

  return {
    supportsImageInputs:
      Boolean(model.supportsImageInputs) ||
      Boolean(inferred.supportsImageInputs) ||
      Boolean(geminiFlags.supportsImageInputs),
    supportsPdfInputs:
      Boolean(model.supportsPdfInputs) || Boolean(geminiFlags.supportsPdfInputs),
    supportsAudioInputs:
      Boolean(model.supportsAudioInputs) || Boolean(geminiFlags.supportsAudioInputs),
    supportsVideoInputs:
      Boolean(model.supportsVideoInputs) ||
      Boolean(inferred.supportsVideoInputs) ||
      Boolean(geminiFlags.supportsVideoInputs)
  }
}

export function modelSupportsMultimodalKind(
  flags: MultimodalCapabilityFlags | null | undefined,
  kind: MultimodalKind
): boolean {
  if (!flags) return false
  switch (kind) {
    case 'image':
      return Boolean(flags.supportsImageInputs)
    case 'file':
      return Boolean(flags.supportsPdfInputs)
    case 'audio':
      return Boolean(flags.supportsAudioInputs)
    case 'video':
      return Boolean(flags.supportsVideoInputs)
    default:
      return false
  }
}

export function unsupportedMultimodalHint(
  kind: MultimodalKind
): string {
  switch (kind) {
    case 'image':
      return 'Active model cannot view images. File was uploaded; switch to a vision model or use read_file.'
    case 'file':
      return 'Active model may not accept PDF/PPT as multimodal input. File was uploaded to the workspace.'
    case 'audio':
      return 'Active model may not accept audio input. File was uploaded to the workspace.'
    case 'video':
      return 'Active model may not accept video input. File was uploaded to the workspace.'
    default:
      return 'File was uploaded to the workspace.'
  }
}
