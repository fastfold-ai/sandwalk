/** Prefer API detail text when present. */
export function formatWorkspaceUploadError(error: unknown): string {
  if (!(error instanceof Error)) return 'Upload failed'
  const raw = error.message || 'Upload failed'
  const jsonStart = raw.indexOf('{')
  if (jsonStart >= 0) {
    try {
      const parsed = JSON.parse(raw.slice(jsonStart)) as { detail?: unknown }
      if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
        return parsed.detail.trim()
      }
    } catch {
      // fall through
    }
  }
  return raw
}
