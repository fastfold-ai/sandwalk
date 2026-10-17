/** "Oct 13, 2026, 2:12 PM (3 days ago)" for a GitHub release timestamp. */
export function formatReleaseAge(
  publishedAt: string,
  now = new Date()
): string | null {
  const date = new Date(publishedAt)
  if (Number.isNaN(date.getTime())) return null
  const formatted = new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  }).format(date)
  const days = Math.floor((now.getTime() - date.getTime()) / 86_400_000)
  const relative =
    days <= 0 ? 'today' : days === 1 ? '1 day ago' : `${days} days ago`
  return `${formatted} (${relative})`
}

/** Published time of the last shipped release (`public/release.json`). */
export async function fetchLastReleaseDate(): Promise<string | null> {
  try {
    const response = await fetch('/release.json', { cache: 'no-store' })
    if (!response.ok) return null
    const body = (await response.json()) as { pub_date?: unknown }
    return typeof body.pub_date === 'string' ? body.pub_date : null
  } catch {
    return null
  }
}
