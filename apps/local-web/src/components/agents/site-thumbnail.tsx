import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { Site } from '@sandwalk/agent-ui-core'
import { Globe2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { cn } from '@/lib/utils'

export function SiteThumbnail({
  client,
  site,
  className
}: {
  client: LocalAgentClient
  site: Site
  className?: string
}) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void client
      .createSitePreviewTicket(site.id, controller.signal)
      .then(ticket => setUrl(ticket.url))
      .catch(() => undefined)
    return () => controller.abort()
  }, [client, site.id, site.updatedAt])

  return (
    <div
      className={cn(
        'border-border bg-muted/30 relative h-14 w-24 shrink-0 overflow-hidden rounded-md border',
        className
      )}
    >
      {url ? (
        <iframe
          title={`${site.name} thumbnail`}
          src={url}
          sandbox=""
          loading="lazy"
          referrerPolicy="no-referrer"
          tabIndex={-1}
          className="pointer-events-none h-[1000%] w-[1000%] origin-top-left scale-[0.1] border-0 bg-white"
        />
      ) : (
        <div className="flex h-full items-center justify-center">
          <Globe2 className="text-muted-foreground size-5" />
        </div>
      )}
      <span className="absolute inset-0" aria-hidden />
    </div>
  )
}
