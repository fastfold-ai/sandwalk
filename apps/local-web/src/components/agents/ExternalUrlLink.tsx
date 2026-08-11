import { type ReactNode,useState } from 'react'

import { openInSystemBrowser } from '@/lib/desktop'
import { faviconCandidatesForUrl } from '@/lib/favicon'
import { cn } from '@/lib/utils'

/** Inline external link with site favicon; opens in the system browser. */
export function ExternalUrlLink({
  href,
  children,
  className
}: {
  href: string
  children?: ReactNode
  className?: string
}) {
  const candidates = faviconCandidatesForUrl(href)
  const [faviconIndex, setFaviconIndex] = useState(0)
  const showFavicon =
    candidates.length > 0 && faviconIndex < candidates.length

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        'text-blue-600 inline items-baseline break-all hover:underline dark:text-blue-400',
        className
      )}
      onClick={event => {
        event.preventDefault()
        void openInSystemBrowser(href)
      }}
    >
      {showFavicon ? (
        <img
          key={candidates[faviconIndex]}
          src={candidates[faviconIndex]}
          alt=""
          className="mr-1 inline-block size-3.5 shrink-0 rounded-sm align-text-bottom"
          onError={() => setFaviconIndex(prev => prev + 1)}
        />
      ) : null}
      {children ?? href}
    </a>
  )
}
