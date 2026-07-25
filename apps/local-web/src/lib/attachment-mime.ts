/** Guess a MIME type from a workspace path / filename for composer attachment thumbs. */

export function contentTypeFromPath(path: string): string {
  const name = path.split('/').at(-1) || path
  const ext = name.includes('.')
    ? name.split('.').pop()!.toLowerCase()
    : ''
  switch (ext) {
    case 'png':
      return 'image/png'
    case 'jpg':
    case 'jpeg':
      return 'image/jpeg'
    case 'gif':
      return 'image/gif'
    case 'webp':
      return 'image/webp'
    case 'svg':
      return 'image/svg+xml'
    case 'bmp':
      return 'image/bmp'
    case 'tif':
    case 'tiff':
      return 'image/tiff'
    case 'mp4':
      return 'video/mp4'
    case 'webm':
      return 'video/webm'
    case 'mov':
      return 'video/quicktime'
    case 'mp3':
      return 'audio/mpeg'
    case 'wav':
      return 'audio/wav'
    case 'pdf':
      return 'application/pdf'
    default:
      return 'application/octet-stream'
  }
}

export function needsAttachmentPreview(contentType: string, path: string) {
  if (contentType.startsWith('image/') || contentType.startsWith('video/')) {
    return true
  }
  return /\.(png|jpe?g|gif|webp|svg|bmp|tiff?|mp4|webm|mov)$/i.test(path)
}
