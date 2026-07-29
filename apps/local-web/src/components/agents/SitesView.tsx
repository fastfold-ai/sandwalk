import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession, Site } from '@sandwalk/agent-ui-core'
import {
  ExternalLink,
  Globe2,
  LayoutGrid,
  List,
  Loader2,
  Pencil,
  Plus,
  Rocket,
  Trash2
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import {
  SitesViewGrid,
  SitesViewList
} from '@/components/agents/sites-view-list'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { isTauri, openExternalUrl } from '@/lib/desktop'
import {
  filterSites,
  formatSiteBytes,
  isPublishedSite,
  siteChatPath,
  sitePublicUrl,
  siteSourceLabel
} from '@/lib/sites'
import { cn } from '@/lib/utils'

const LAYOUT_KEY = 'sandwalk.sites.layout'

function formatUpdated(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Recently'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year:
      date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric'
  }).format(date)
}

function formatSiteCount(total: number) {
  return `${total.toLocaleString()} ${total === 1 ? 'site' : 'sites'}`
}

function statusLabel(site: Site) {
  if (site.status === 'published' && site.deployment?.status === 'published') {
    return 'Published'
  }
  if (site.status === 'publishing') return 'Publishing'
  if (site.status === 'error') return 'Error'
  if (site.status === 'ready') return 'Ready'
  return 'Draft'
}

function SiteActions({
  site,
  busy,
  onPreview,
  onOpen,
  onPublish,
  onRename,
  onDelete
}: {
  site: Site
  busy: boolean
  onPreview: () => void
  onOpen: () => void
  onPublish: () => void
  onRename: () => void
  onDelete: () => void
}) {
  const published = isPublishedSite(site)
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Button variant="outline" size="sm" onClick={onPreview} disabled={busy}>
        Preview
      </Button>
      {published ? (
        <Button variant="outline" size="sm" onClick={onOpen} disabled={busy}>
          <ExternalLink className="mr-1.5 size-3.5" />
          Open
        </Button>
      ) : null}
      <Button size="sm" onClick={onPublish} disabled={busy}>
        {busy ? (
          <Loader2 className="mr-1.5 size-3.5 animate-spin" />
        ) : (
          <Rocket className="mr-1.5 size-3.5" />
        )}
        {published ? 'Republish' : 'Publish'}
      </Button>
      <Button variant="ghost" size="icon" onClick={onRename} disabled={busy}>
        <Pencil className="size-3.5" />
        <span className="sr-only">Rename</span>
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="text-destructive hover:text-destructive"
        onClick={onDelete}
        disabled={busy}
      >
        <Trash2 className="size-3.5" />
        <span className="sr-only">Delete</span>
      </Button>
    </div>
  )
}

export function SitesView({
  client,
  navigate,
  siteId,
  sessions,
  projects,
  onAddSite
}: {
  client: LocalAgentClient
  navigate: NavigateFunction
  siteId: string | null
  sessions: AgentSession[]
  projects: AgentProject[]
  onAddSite: () => void
}) {
  const [sites, setSites] = useState<Site[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [layout, setLayout] = useState<'grid' | 'list'>(() => {
    try {
      return localStorage.getItem(LAYOUT_KEY) === 'list' ? 'list' : 'grid'
    } catch {
      return 'grid'
    }
  })
  const [busyId, setBusyId] = useState<string | null>(null)
  const [preview, setPreview] = useState<{ site: Site; url: string } | null>(
    null
  )
  const [rename, setRename] = useState<Site | null>(null)
  const [renameValue, setRenameValue] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await client.listSites()
      setSites(data)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load sites.')
    } finally {
      setLoading(false)
    }
  }, [client])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    try {
      localStorage.setItem(LAYOUT_KEY, layout)
    } catch {
      // Sandboxed or privacy-restricted views may not expose storage.
    }
  }, [layout])

  const filtered = useMemo(() => filterSites(sites, query), [query, sites])
  const selected = siteId
    ? sites.find(site => site.id === siteId) ?? null
    : null

  useEffect(() => {
    if (!siteId || !selected) return
    navigate(siteChatPath(selected) ?? '/sites', { replace: true })
  }, [navigate, selected, siteId])

  const replaceSite = (site: Site) => {
    setSites(current =>
      current.some(item => item.id === site.id)
        ? current.map(item => (item.id === site.id ? site : item))
        : [site, ...current]
    )
  }

  const run = async (site: Site, action: () => Promise<Site>) => {
    setBusyId(site.id)
    setError(null)
    try {
      replaceSite(await action())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Site action failed.')
    } finally {
      setBusyId(null)
    }
  }

  const showPreview = async (site: Site) => {
    setBusyId(site.id)
    setError(null)
    try {
      const ticket = await client.createSitePreviewTicket(site.id)
      setPreview({ site, url: ticket.url })
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not create preview.'
      )
    } finally {
      setBusyId(null)
    }
  }

  const openPublished = async (site: Site) => {
    const url = sitePublicUrl(site)
    if (!url) return
    if (isTauri()) {
      await openExternalUrl(url)
      return
    }
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  const deleteSite = async (site: Site) => {
    if (!window.confirm(`Delete “${site.name}”? This cannot be undone.`)) return
    setBusyId(site.id)
    setError(null)
    try {
      await client.deleteSite(site.id)
      setSites(current => current.filter(item => item.id !== site.id))
      if (siteId === site.id) navigate('/sites')
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not delete site.'
      )
    } finally {
      setBusyId(null)
    }
  }

  const submitRename = async () => {
    const site = rename
    const name = renameValue.trim()
    if (!site || !name) return
    setRename(null)
    await run(site, () => client.updateSite(site.id, { name }))
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="text-muted-foreground size-5 animate-spin" />
      </div>
    )
  }

  if (siteId && !selected) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3">
        <Globe2 className="text-muted-foreground size-8" />
        <p className="text-sm font-medium">Site not found</p>
        <Button variant="outline" onClick={() => navigate('/sites')}>
          Back to Sites
        </Button>
      </div>
    )
  }

  const actions = (site: Site) => (
    <SiteActions
      site={site}
      busy={busyId === site.id}
      onPreview={() => void showPreview(site)}
      onOpen={() => void openPublished(site)}
      onPublish={() =>
        void run(site, () => client.publishSite(site.id, { slug: site.slug }))
      }
      onRename={() => {
        setRename(site)
        setRenameValue(site.name)
      }}
      onDelete={() => void deleteSite(site)}
    />
  )
  const viewProps = {
    client,
    sites: filtered,
    sessions,
    projects,
    busyId,
    onSelect: (site: Site) => {
      const path = siteChatPath(site)
      if (!path) {
        void showPreview(site)
        return
      }
      navigate(path)
    },
    onPreview: (site: Site) => void showPreview(site),
    onOpen: (site: Site) => void openPublished(site),
    onPublish: (site: Site) =>
      void run(site, () =>
        client.publishSite(site.id, { slug: site.slug })
      ),
    onRename: (site: Site) => {
      setRename(site)
      setRenameValue(site.name)
    },
    onDelete: (site: Site) => void deleteSite(site)
  }

  return (
    <>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <header className="mx-auto flex w-full max-w-6xl shrink-0 items-center justify-between gap-3 px-6 pb-6 pt-3 md:px-10">
          <div className="flex min-w-0 items-center gap-2.5">
            <Globe2 className="text-muted-foreground size-5 shrink-0" />
            <h1 className="text-lg font-semibold tracking-tight">
              {selected ? selected.name : 'Sites'}
            </h1>
            {!selected ? (
              <span className="text-muted-foreground text-sm leading-none tabular-nums">
                {formatSiteCount(sites.length)}
              </span>
            ) : null}
          </div>
          {selected ? (
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/sites')}
              >
                All sites
              </Button>
              {actions(selected)}
            </div>
          ) : (
            <div className="flex items-center gap-1">
              <Input
                value={query}
                onChange={event => setQuery(event.target.value)}
                placeholder="Search sites"
                className="h-8 w-44 md:w-56"
              />
              <Button size="sm" className="h-8" onClick={onAddSite}>
                <Plus className="mr-1.5 size-3.5" />
                Add
              </Button>
              <div className="flex items-center">
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className={cn('size-8', layout === 'grid' && 'bg-muted')}
                  onClick={() => setLayout('grid')}
                  aria-label="Gallery view"
                >
                  <LayoutGrid className="size-3.5" />
                </Button>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className={cn('size-8', layout === 'list' && 'bg-muted')}
                  onClick={() => setLayout('list')}
                  aria-label="List view"
                >
                  <List className="size-3.5" />
                </Button>
              </div>
            </div>
          )}
        </header>

        {error ? (
          <div className="mx-auto w-full max-w-6xl px-6 pb-4 md:px-10">
            <div className="border-destructive/30 bg-destructive/5 text-destructive rounded-md border px-3 py-2 text-xs">
              {error}
            </div>
          </div>
        ) : null}

        {selected ? (
          <main className="min-h-0 flex-1 overflow-auto p-6">
            <div className="mx-auto grid max-w-5xl gap-5 lg:grid-cols-[1fr_18rem]">
              <button
                type="button"
                className="border-border bg-muted/20 hover:border-foreground/25 aspect-video overflow-hidden rounded-xl border text-left transition-colors"
                onClick={() => void showPreview(selected)}
              >
                <div className="flex h-full flex-col items-center justify-center gap-3">
                  <Globe2 className="text-muted-foreground size-10" />
                  <span className="text-sm font-medium">
                    Preview local site
                  </span>
                  <span className="text-muted-foreground text-xs">
                    Opens in an isolated sandbox
                  </span>
                </div>
              </button>
              <aside className="border-border rounded-xl border p-4">
                <h2 className="text-sm font-medium">Site details</h2>
                <dl className="mt-4 space-y-4 text-xs">
                  <div>
                    <dt className="text-muted-foreground">Status</dt>
                    <dd className="mt-1 font-medium">
                      {statusLabel(selected)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Source</dt>
                    <dd className="mt-1 font-medium">
                      {siteSourceLabel(selected, sessions, projects)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Slug</dt>
                    <dd className="mt-1 font-mono">
                      {selected.slug || 'Assigned on publish'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Public URL</dt>
                    <dd className="mt-1 break-all">
                      {sitePublicUrl(selected) || 'Not published'}
                    </dd>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <dt className="text-muted-foreground">Size</dt>
                      <dd className="mt-1">
                        {formatSiteBytes(
                          selected.deployment?.sizeBytes ?? selected.sizeBytes
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Updated</dt>
                      <dd className="mt-1">
                        {formatUpdated(selected.updatedAt)}
                      </dd>
                    </div>
                  </div>
                </dl>
              </aside>
            </div>
          </main>
        ) : (
          <main className="min-h-0 flex-1 overflow-auto">
            <div className="mx-auto w-full max-w-6xl px-6 pb-10 md:px-10">
              {filtered.length ? (
                layout === 'grid' ? (
                  <SitesViewGrid {...viewProps} />
                ) : (
                  <SitesViewList {...viewProps} />
                )
              ) : (
                <div className="border-border flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed">
                  <Globe2 className="text-muted-foreground size-8" />
                  <p className="mt-3 text-sm font-medium">
                    {query ? 'No matching sites' : 'No sites yet'}
                  </p>
                  <p className="text-muted-foreground mt-1 text-xs">
                    Sites built by agents will appear here.
                  </p>
                  {!query ? (
                    <Button size="sm" className="mt-4" onClick={onAddSite}>
                      <Plus className="mr-1.5 size-3.5" />
                      Add site
                    </Button>
                  ) : null}
                </div>
              )}
            </div>
          </main>
        )}
      </div>

      <Dialog
        open={Boolean(preview)}
        onOpenChange={open => !open && setPreview(null)}
      >
        <DialogContent className="h-[85vh] max-w-[92vw] gap-0 overflow-hidden p-0">
          <DialogHeader className="border-border border-b px-4 py-3">
            <DialogTitle className="text-sm">{preview?.site.name}</DialogTitle>
            <DialogDescription className="text-xs">
              Sandboxed local preview
            </DialogDescription>
          </DialogHeader>
          {preview ? (
            <iframe
              title={`${preview.site.name} preview`}
              src={preview.url}
              sandbox="allow-forms allow-modals allow-popups allow-scripts"
              referrerPolicy="no-referrer"
              className="h-full min-h-0 w-full bg-white"
            />
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(rename)}
        onOpenChange={open => !open && setRename(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename site</DialogTitle>
            <DialogDescription>
              This changes the name shown in Sandwalk, not its public URL.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={event => setRenameValue(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') void submitRename()
            }}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRename(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => void submitRename()}
              disabled={!renameValue.trim()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
