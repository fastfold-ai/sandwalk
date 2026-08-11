import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession, Site } from '@sandwalk/agent-ui-core'
import {
  ExternalLink,
  Globe2,
  Loader2,
  MoreHorizontal,
  Pencil,
  Rocket,
  Trash2
} from 'lucide-react'

import { SiteThumbnail } from '@/components/agents/site-thumbnail'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  formatSiteBytes,
  isPublishedSite,
  sitePublicUrl,
  siteSourceLabel
} from '@/lib/sites'

export function SitesViewList({
  client,
  sites,
  sessions,
  projects,
  busyId,
  onSelect,
  onPreview,
  onOpen,
  onPublish,
  onRename,
  onDelete
}: {
  client: LocalAgentClient
  sites: Site[]
  sessions: AgentSession[]
  projects: AgentProject[]
  busyId: string | null
  onSelect: (site: Site) => void
  onPreview: (site: Site) => void
  onOpen: (site: Site) => void
  onPublish: (site: Site) => void
  onRename: (site: Site) => void
  onDelete: (site: Site) => void
}) {
  return (
    <div>
      <div className="text-muted-foreground grid grid-cols-[minmax(0,1fr)_7rem_6rem_auto] items-center gap-6 border-b px-1 pb-2 text-[10px] font-medium uppercase tracking-wider">
        <span>Site</span>
        <span>Status</span>
        <span>Size</span>
        <span className="w-32" />
      </div>
      <div>
        {sites.map(site => {
          const published = isPublishedSite(site)
          const busy = busyId === site.id
          return (
            <div
              key={site.id}
              className="border-border/60 hover:bg-muted/25 grid grid-cols-[minmax(0,1fr)_7rem_6rem_auto] items-center gap-6 border-b px-1 py-3 transition-colors"
            >
              <button
                type="button"
                className="flex min-w-0 items-center gap-3 text-left"
                onClick={() => onSelect(site)}
              >
                <SiteThumbnail client={client} site={site} />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">
                    {site.name}
                  </span>
                  <span className="text-muted-foreground mt-1 block truncate text-xs">
                    {siteSourceLabel(site, sessions, projects)}
                    {sitePublicUrl(site) ? ` · ${sitePublicUrl(site)}` : ''}
                  </span>
                </span>
              </button>

              <span className="text-muted-foreground text-xs">
                {published ? 'Published' : 'Not published'}
              </span>

              <span className="text-muted-foreground text-xs">
                {formatSiteBytes(
                  site.deployment?.sizeBytes ?? site.sizeBytes
                )}
              </span>

              <div className="flex w-32 items-center justify-end gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8"
                  disabled={busy}
                  onClick={() => (published ? onOpen(site) : onPublish(site))}
                >
                  {busy ? (
                    <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                  ) : published ? (
                    <ExternalLink className="mr-1.5 size-3.5" />
                  ) : (
                    <Rocket className="mr-1.5 size-3.5" />
                  )}
                  {published ? 'Open' : 'Publish'}
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      disabled={busy}
                      aria-label={`Actions for ${site.name}`}
                    >
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => onPreview(site)}>
                      <Globe2 className="mr-2 size-3.5" />
                      Preview
                    </DropdownMenuItem>
                    {published ? (
                      <DropdownMenuItem onClick={() => onPublish(site)}>
                        <Rocket className="mr-2 size-3.5" />
                        Republish
                      </DropdownMenuItem>
                    ) : null}
                    <DropdownMenuItem onClick={() => onRename(site)}>
                      <Pencil className="mr-2 size-3.5" />
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => onDelete(site)}
                    >
                      <Trash2 className="mr-2 size-3.5" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function SitesViewGrid({
  client,
  sites,
  sessions,
  projects,
  busyId,
  onSelect,
  onPreview,
  onOpen,
  onPublish,
  onRename,
  onDelete
}: {
  client: LocalAgentClient
  sites: Site[]
  sessions: AgentSession[]
  projects: AgentProject[]
  busyId: string | null
  onSelect: (site: Site) => void
  onPreview: (site: Site) => void
  onOpen: (site: Site) => void
  onPublish: (site: Site) => void
  onRename: (site: Site) => void
  onDelete: (site: Site) => void
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      {sites.map(site => {
        const published = isPublishedSite(site)
        const busy = busyId === site.id
        return (
          <article
            key={site.id}
            className="group border-border/70 overflow-hidden rounded-xl border bg-background"
          >
            <button
              type="button"
              className="block w-full text-left"
              onClick={() => onSelect(site)}
            >
              <SiteThumbnail
                client={client}
                site={site}
                className="aspect-video h-auto w-full rounded-none border-0 border-b"
              />
              <span className="block p-2.5 pb-2">
                <span className="block truncate text-[13px] font-medium">
                  {site.name}
                </span>
                <span className="text-muted-foreground mt-0.5 block truncate text-[11px]">
                  {siteSourceLabel(site, sessions, projects)}
                </span>
              </span>
            </button>

            <div className="flex items-center justify-between gap-1 px-2.5 pb-2.5">
              <span className="text-muted-foreground min-w-0 truncate text-[10px]">
                {published ? 'Published' : 'Not published'} ·{' '}
                {formatSiteBytes(
                  site.deployment?.sizeBytes ?? site.sizeBytes
                )}
              </span>
              <div className="flex shrink-0 items-center gap-0.5">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  disabled={busy}
                  onClick={() => (published ? onOpen(site) : onPublish(site))}
                  aria-label={published ? `Open ${site.name}` : `Publish ${site.name}`}
                >
                  {busy ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : published ? (
                    <ExternalLink className="size-3.5" />
                  ) : (
                    <Rocket className="size-3.5" />
                  )}
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-7"
                      disabled={busy}
                      aria-label={`Actions for ${site.name}`}
                    >
                      <MoreHorizontal className="size-3.5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => onPreview(site)}>
                      <Globe2 className="mr-2 size-3.5" />
                      Preview
                    </DropdownMenuItem>
                    {published ? (
                      <DropdownMenuItem onClick={() => onPublish(site)}>
                        <Rocket className="mr-2 size-3.5" />
                        Republish
                      </DropdownMenuItem>
                    ) : null}
                    <DropdownMenuItem onClick={() => onRename(site)}>
                      <Pencil className="mr-2 size-3.5" />
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => onDelete(site)}
                    >
                      <Trash2 className="mr-2 size-3.5" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </article>
        )
      })}
    </div>
  )
}
