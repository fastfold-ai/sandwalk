import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { Site } from '@sandwalk/agent-ui-core'
import { ExternalLink, Globe2, Loader, RefreshCw, Rocket, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { openInSystemBrowser } from '@/lib/desktop'
import { SITE_PREVIEW_SANDBOX } from '@/lib/sites'

export function SitePreviewPanel({
  client,
  sessionId,
  workspaceVersion,
  runActive,
  siteId = null,
  onClose
}: {
  client: LocalAgentClient
  sessionId: string
  workspaceVersion: number
  runActive: boolean
  siteId?: string | null
  onClose?: () => void
}) {
  const [sites, setSites] = useState<Site[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [preview, setPreview] = useState<{
    url: string
    expiresAt: string | null
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [previewing, setPreviewing] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refresh, setRefresh] = useState(0)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const data = await client.listSites({ signal })
        const matches = data
          .filter(site => site.sourceSessionId === sessionId)
          .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
        setSites(matches)
        setSelectedId(current =>
          siteId && matches.some(site => site.id === siteId)
            ? siteId
            : current && matches.some(site => site.id === current)
              ? current
              : (matches[0]?.id ?? null)
        )
        setError(null)
      } catch (cause) {
        if (signal?.aborted) return
        setError(
          cause instanceof Error ? cause.message : 'Could not load site previews.'
        )
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [client, sessionId, siteId]
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    const interval = runActive
      ? window.setInterval(() => void load(controller.signal), 2_000)
      : null
    return () => {
      controller.abort()
      if (interval !== null) window.clearInterval(interval)
    }
  }, [load, runActive, workspaceVersion])

  const selected = useMemo(
    () => sites.find(site => site.id === selectedId) ?? sites[0] ?? null,
    [selectedId, sites]
  )

  useEffect(() => {
    if (!selected) {
      setPreview(null)
      return
    }
    const controller = new AbortController()
    setPreviewing(true)
    void client
      .createSitePreviewTicket(selected.id, controller.signal)
      .then(ticket => {
        setPreview(ticket)
        setError(null)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(
          cause instanceof Error
            ? cause.message
            : 'Could not create the local preview.'
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setPreviewing(false)
      })
    return () => controller.abort()
  }, [client, refresh, selected?.id, selected?.updatedAt])

  useEffect(() => {
    if (!preview?.expiresAt) return
    const remaining = Date.parse(preview.expiresAt) - Date.now() - 30_000
    const timeout = window.setTimeout(
      () => setRefresh(current => current + 1),
      Math.max(1_000, remaining)
    )
    return () => window.clearTimeout(timeout)
  }, [preview?.expiresAt])

  const reload = () => {
    void load().finally(() => setRefresh(current => current + 1))
  }
  const publish = async () => {
    if (!selected) return
    setPublishing(true)
    setPublishError(null)
    try {
      const updated = await client.publishSite(selected.id, {
        slug: selected.slug
      })
      setSites(current =>
        current.map(site => (site.id === updated.id ? updated : site))
      )
    } catch (cause) {
      setPublishError(
        cause instanceof Error ? cause.message : 'Could not publish site.'
      )
    } finally {
      setPublishing(false)
    }
  }
  const publishedUrl = selected?.deployment?.publicUrl ?? null

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="sandwalk-shell-nav-strip relative z-20 flex shrink-0 items-center gap-1 px-1.5">
        <div className="chat-scrollbar-x flex min-w-0 flex-1 items-stretch overflow-x-auto">
          <div className="text-foreground my-auto flex h-8 w-[180px] max-w-[240px] shrink-0 items-center gap-1.5 px-1">
            <Globe2 className="size-3.5 shrink-0" />
            {sites.length > 1 ? (
              <select
                aria-label="Preview site"
                value={selected?.id ?? ''}
                onChange={event => setSelectedId(event.target.value)}
                className="min-w-0 flex-1 truncate border-0 bg-transparent p-0 text-xs font-medium outline-none"
              >
                {sites.map(site => (
                  <option key={site.id} value={site.id}>
                    {site.name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="min-w-0 truncate text-xs font-medium">
                {selected?.name ?? 'Site preview'}
              </span>
            )}
          </div>
        </div>
        <div className="ml-auto flex shrink-0 items-center">
          <span
            className={`mr-1.5 text-[11px] ${
              publishError ? 'text-destructive' : 'text-muted-foreground'
            }`}
            title={publishError ?? undefined}
          >
            {publishError
              ? 'Publish failed'
              : publishing
              ? 'Publishing…'
              : publishedUrl
                ? 'Published'
                : 'Not published'}
          </span>
          {publishedUrl ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 max-w-52 gap-1.5 px-2 text-xs"
              onClick={() => void openInSystemBrowser(publishedUrl)}
              aria-label={`Open published site ${publishedUrl}`}
              title={publishedUrl}
            >
              <ExternalLink className="size-3.5 shrink-0" />
              <span className="truncate">{publishedUrl}</span>
            </Button>
          ) : (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 text-xs"
              onClick={() => void publish()}
              disabled={!selected || publishing}
            >
              {publishing ? (
                <Loader className="size-3.5 animate-spin" />
              ) : (
                <Rocket className="size-3.5" />
              )}
              Publish
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={reload}
            disabled={!selected}
            aria-label="Refresh site preview"
            title="Refresh site preview"
          >
            <RefreshCw
              className={`size-3.5 ${previewing ? 'animate-spin' : ''}`}
            />
          </Button>
          {onClose ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={onClose}
              aria-label="Hide site preview"
              title="Hide site preview"
            >
              <X className="size-3.5" />
            </Button>
          ) : null}
        </div>
      </header>

      {loading ? (
        <div className="text-muted-foreground flex min-h-0 flex-1 items-center justify-center gap-2 text-xs">
          <Loader className="size-4 animate-spin" />
          Loading sites…
        </div>
      ) : error && !preview ? (
        <div className="text-destructive flex min-h-0 flex-1 items-center justify-center p-6 text-center text-xs">
          {error}
        </div>
      ) : !selected ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
          <Globe2 className="text-muted-foreground size-8" />
          <p className="text-sm font-medium">No site for this session yet</p>
          <p className="text-muted-foreground max-w-64 text-xs">
            Ask the agent to build a site. Its managed local preview will appear
            here after registration.
          </p>
        </div>
      ) : preview ? (
        <iframe
          key={`${selected.id}-${selected.updatedAt}-${preview.url}`}
          title={`${selected.name} preview`}
          src={preview.url}
          sandbox={SITE_PREVIEW_SANDBOX}
          referrerPolicy="no-referrer"
          className="min-h-0 flex-1 bg-white"
        />
      ) : (
        <div className="text-muted-foreground flex min-h-0 flex-1 items-center justify-center gap-2 text-xs">
          <Loader className="size-4 animate-spin" />
          Preparing preview…
        </div>
      )}
    </div>
  )
}
