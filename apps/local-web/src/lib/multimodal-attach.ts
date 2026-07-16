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
