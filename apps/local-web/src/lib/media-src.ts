/** Build a blob/object URL from a workspace file payload for media elements. */

export function videoMimeFromName(name: string, fallback?: string | null): string {
  if (fallback && fallback.startsWith('video/')) return fallback
  const ext = name.includes('.')
    ? name.split('.').pop()!.toLowerCase()
    : ''
  switch (ext) {
    case 'webm':
      return 'video/webm'
    case 'mov':
      return 'video/quicktime'
    case 'avi':
      return 'video/x-msvideo'
    case 'mpeg':
    case 'mpg':
      return 'video/mpeg'
    case '3gpp':
      return 'video/3gpp'
    case 'wmv':
      return 'video/x-ms-wmv'
    case 'flv':
      return 'video/x-flv'
    case 'mp4':
    default:
      return 'video/mp4'
  }
}

export function audioMimeFromName(name: string, fallback?: string | null): string {
  if (fallback && fallback.startsWith('audio/')) return fallback
  const ext = name.includes('.')
    ? name.split('.').pop()!.toLowerCase()
    : ''
  switch (ext) {
    case 'wav':
      return 'audio/wav'
    case 'aiff':
    case 'aif':
      return 'audio/aiff'
    case 'aac':
      return 'audio/aac'
    case 'ogg':
      return 'audio/ogg'
    case 'flac':
      return 'audio/flac'
    case 'm4a':
      return 'audio/mp4'
    case 'mp3':
    default:
      return 'audio/mpeg'
  }
}

function mimeFromName(name: string, fallback?: string | null): string {
  if (fallback && fallback !== 'application/octet-stream') return fallback
  const ext = name.includes('.')
    ? name.split('.').pop()!.toLowerCase()
    : ''
  if (
    ['mp4', 'webm', 'mov', 'avi', 'mpeg', 'mpg', 'wmv', 'flv', '3gpp'].includes(
      ext
    )
  ) {
    return videoMimeFromName(name, fallback)
  }
  if (
    ['mp3', 'wav', 'aiff', 'aif', 'aac', 'ogg', 'flac', 'm4a'].includes(ext)
  ) {
    return audioMimeFromName(name, fallback)
  }
  return fallback || 'application/octet-stream'
}

export function mediaObjectUrlFromFile(file: {
  encoding: string
  content: string
  mimeType?: string | null
  name?: string
}): string {
  const mime = mimeFromName(file.name || '', file.mimeType)
  if (file.encoding === 'base64') {
    const binary = atob(file.content)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i)
    }
    return URL.createObjectURL(new Blob([bytes], { type: mime }))
  }
  return URL.createObjectURL(new Blob([file.content], { type: mime }))
}
