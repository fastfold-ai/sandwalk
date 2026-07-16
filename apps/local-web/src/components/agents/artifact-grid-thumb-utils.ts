export type ThumbKind =
  | 'image'
  | 'video'
  | 'audio'
  | 'structure'
  | 'text'
  | 'table'
  | 'icon'

export function extensionOf(name: string) {
  const parts = name.toLowerCase().split('.')
  return parts.length > 1 ? parts.at(-1) || '' : ''
}

export function classify(name: string): ThumbKind {
  const ext = extensionOf(name)
  if (
    ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'ico'].includes(ext)
  ) {
    return 'image'
  }
  if (
    ['mp4', 'webm', 'mov', 'avi', 'mpeg', 'mpg', 'wmv', 'flv', '3gpp'].includes(
      ext
    )
  ) {
    return 'video'
  }
  if (['mp3', 'wav', 'aiff', 'aif', 'aac', 'ogg', 'flac', 'm4a'].includes(ext)) {
    return 'audio'
  }
  if (['pdb', 'cif', 'mmcif', 'sdf'].includes(ext)) return 'structure'
  if (['csv', 'tsv'].includes(ext)) return 'table'
  if (
    [
      'json',
      'md',
      'txt',
      'yaml',
      'yml',
      'py',
      'ts',
      'tsx',
      'js',
      'jsx',
      'css',
      'html',
      'htm',
      'xml',
      'log'
    ].includes(ext)
  ) {
    return 'text'
  }
  return 'icon'
}

export function structureFormat(name: string): 'pdb' | 'cif' | 'sdf' {
  const lower = name.toLowerCase()
  if (lower.endsWith('.pdb')) return 'pdb'
  if (lower.endsWith('.sdf')) return 'sdf'
  return 'cif'
}

export function decodeContent(encoding: 'text' | 'base64', content: string) {
  if (encoding === 'text') return content
  try {
    return atob(content)
  } catch {
    return content
  }
}
