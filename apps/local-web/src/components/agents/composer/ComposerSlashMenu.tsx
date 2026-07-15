import type {
  AgentSkill,
  AgentSkillDetail,
  McpServer,
  Specialist
} from '@sandwalk/agent-ui-core'
import { CornerDownLeft, Plug, Sparkles } from 'lucide-react'
import {
  forwardRef,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState} from 'react'

import {
  buildSlashResults,
  cleanSkillDescription,
  mcpIconForServer,
  type SlashItem
} from '@/components/agents/composer/composer-mention-utils'
import {
  extractSkillOverviewFromMarkdown,
  getSkillPromptExamples
} from '@/components/agents/skill-examples'
import { ScrollArea } from '@/components/ui/scroll-area'
import { composerSkillIcon, skillIconInvertInDark } from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

export type ComposerSlashMenuHandle = {
  handleKeyDown: (event: KeyboardEvent) => boolean
}

export const ComposerSlashMenu = forwardRef<
  ComposerSlashMenuHandle,
  {
    open: boolean
    slash: { query: string } | null
    skills: AgentSkill[]
    mcpServers: McpServer[]
    selectedSpecialist: Specialist | null
    onLoadSkill: (name: string) => Promise<AgentSkillDetail>
    onPickSkill: (skill: AgentSkill) => void
    onPickMcp: (server: McpServer) => void
    onPickExample: (skillName: string, prompt: string) => void
    onDismiss: () => void
    focusInput: () => void
  }
>(function ComposerSlashMenu(
  {
    open,
    slash,
    skills,
    mcpServers,
    selectedSpecialist,
    onLoadSkill,
    onPickSkill,
    onPickMcp,
    onPickExample,
    onDismiss,
    focusInput
  },
  ref
) {
  const [selectedSlashKey, setSelectedSlashKey] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewOverview, setPreviewOverview] = useState<string | null>(null)
  const previewCacheRef = useRef<Map<string, string>>(new Map())
  const slashItemRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const listRootRef = useRef<HTMLDivElement | null>(null)

  const slashResults = useMemo(
    () =>
      buildSlashResults({
        slash,
        skills,
        mcpServers,
        selectedSpecialist
      }),
    [mcpServers, selectedSpecialist, skills, slash]
  )

  const selectedSlashItem =
    slashResults.find(item => item.key === selectedSlashKey) ||
    slashResults[0] ||
    null
  const selectedSkill =
    selectedSlashItem?.kind === 'skill' ? selectedSlashItem.skill : null
  const selectedMcp =
    selectedSlashItem?.kind === 'mcp' ? selectedSlashItem.server : null
  const selectedSkillName = selectedSkill?.name ?? null
  const selectedMcpId = selectedMcp?.id ?? null
  const selectedExamples = selectedSkill
    ? getSkillPromptExamples(selectedSkill.name)
    : []

  const scrollSlashItemIntoView = useCallback((key: string) => {
    const node = slashItemRefs.current.get(key)
    const viewport = listRootRef.current?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (!node || !viewport) return
    const nodeRect = node.getBoundingClientRect()
    const viewRect = viewport.getBoundingClientRect()
    const pad = 6
    if (nodeRect.bottom > viewRect.bottom - pad) {
      viewport.scrollTop += nodeRect.bottom - viewRect.bottom + pad
    } else if (nodeRect.top < viewRect.top + pad) {
      viewport.scrollTop -= viewRect.top - nodeRect.top + pad
    }
  }, [])

  useEffect(() => {
    if (!open) {
      setSelectedSlashKey(null)
      return
    }
    if (
      selectedSlashKey &&
      slashResults.some(item => item.key === selectedSlashKey)
    ) {
      return
    }
    const nextKey = slashResults[0]?.key || null
    setSelectedSlashKey(current => (current === nextKey ? current : nextKey))
  }, [open, selectedSlashKey, slashResults])

  useEffect(() => {
    if (!open || !selectedSkillName) {
      if (!selectedMcpId) {
        setPreviewOverview(null)
        setPreviewLoading(false)
      }
      return
    }
    const fallbackDescription = selectedSkill?.description
    const cached = previewCacheRef.current.get(selectedSkillName)
    if (cached) {
      setPreviewOverview(current => (current === cached ? current : cached))
      setPreviewLoading(false)
      return
    }
    let active = true
    setPreviewLoading(true)
    void onLoadSkill(selectedSkillName)
      .then(detail => {
        if (!active) return
        const overview =
          extractSkillOverviewFromMarkdown(detail.content) ||
          cleanSkillDescription(detail.description) ||
          `Use /${detail.name} to run this skill.`
        previewCacheRef.current.set(selectedSkillName, overview)
        setPreviewOverview(overview)
      })
      .catch(() => {
        if (!active) return
        const fallback =
          cleanSkillDescription(fallbackDescription || '') ||
          `Use /${selectedSkillName} to run this skill.`
        setPreviewOverview(fallback)
      })
      .finally(() => {
        if (active) setPreviewLoading(false)
      })
    return () => {
      active = false
    }
    // selectedSkill identity changes every slashResults rebuild; key off name only.
  }, [onLoadSkill, selectedMcpId, selectedSkillName, open])

  useEffect(() => {
    if (!open || !selectedMcpId || !selectedMcp) return
    const overview =
      String(selectedMcp.description || '').trim() ||
      `Mention mcp:${selectedMcp.name} so the agent prefers tools from this MCP server.`
    setPreviewLoading(false)
    setPreviewOverview(current => (current === overview ? current : overview))
    // selectedMcpId gates the preview (selectedMcp object identity is unstable).
  }, [selectedMcpId, open])

  useEffect(() => {
    if (!open || !selectedSlashItem) return
    scrollSlashItemIntoView(selectedSlashItem.key)
  }, [open, scrollSlashItemIntoView, selectedSlashItem?.key])

  const insertSlashItem = (item: SlashItem) => {
    if (item.kind === 'skill') onPickSkill(item.skill)
    else onPickMcp(item.server)
  }

  useImperativeHandle(
    ref,
    () => ({
      handleKeyDown: event => {
        if (!open) return false
        if (event.key === 'Escape') {
          event.preventDefault()
          onDismiss()
          setSelectedSlashKey(null)
          return true
        }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault()
          event.stopPropagation()
          if (slashResults.length === 0) return true
          const currentIndex = slashResults.findIndex(
            item => item.key === selectedSlashItem?.key
          )
          const safeIndex = currentIndex < 0 ? 0 : currentIndex
          const nextIndex =
            event.key === 'ArrowDown'
              ? Math.min(safeIndex + 1, slashResults.length - 1)
              : Math.max(safeIndex - 1, 0)
          const nextKey = slashResults[nextIndex]?.key
          if (!nextKey) return true
          setSelectedSlashKey(nextKey)
          window.requestAnimationFrame(() => {
            focusInput()
            scrollSlashItemIntoView(nextKey)
          })
          return true
        }
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault()
          if (selectedSlashItem) insertSlashItem(selectedSlashItem)
          return true
        }
        return false
      }
    }),
    [
      focusInput,
      onDismiss,
      onPickMcp,
      onPickSkill,
      open,
      scrollSlashItemIntoView,
      selectedSlashItem,
      slashResults
    ]
  )

  if (!open) return null

  return (
    <div className="bg-popover border-border/70 absolute bottom-full left-0 right-0 z-40 mb-2 overflow-hidden rounded-lg border shadow-lg">
      {selectedSpecialist ? (
        <div className="border-border/60 text-muted-foreground border-b px-3 py-1.5 text-[11px]">
          Showing skills & MCPs for{' '}
          <span className="text-foreground font-medium">
            {selectedSpecialist.name}
          </span>
        </div>
      ) : null}
      <div className="grid h-72 grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div ref={listRootRef} className="min-h-0 min-w-0">
          <ScrollArea className="border-border/60 h-72 border-r">
            <div className="p-1" role="listbox" aria-label="Skills and MCPs">
              {slashResults.length > 0 ? (
                slashResults.map(item => {
                  const isSelected = selectedSlashItem?.key === item.key
                  if (item.kind === 'mcp') {
                    const { server } = item
                    const description =
                      String(server.description || '').trim() ||
                      server.transport
                    const icon = mcpIconForServer(server)
                    return (
                      <button
                        key={item.key}
                        type="button"
                        tabIndex={-1}
                        role="option"
                        aria-selected={isSelected}
                        ref={node => {
                          if (node) slashItemRefs.current.set(item.key, node)
                          else slashItemRefs.current.delete(item.key)
                        }}
                        onMouseDown={event => event.preventDefault()}
                        onMouseEnter={() => setSelectedSlashKey(item.key)}
                        onClick={() => {
                          onPickMcp(server)
                        }}
                        className={cn(
                          'hover:bg-muted flex w-full flex-col rounded-md px-2 py-1.5 text-left',
                          isSelected && 'bg-muted'
                        )}
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          {icon ? (
                            <img
                              src={icon.src}
                              alt=""
                              className={cn(
                                'size-[18px] shrink-0 rounded object-contain',
                                icon.invertInDark && 'dark:invert'
                              )}
                            />
                          ) : (
                            <span className="bg-muted text-muted-foreground inline-flex size-[18px] shrink-0 items-center justify-center rounded">
                              <Plug className="size-3" />
                            </span>
                          )}
                          <span className="truncate text-sm font-medium">
                            {server.name}
                          </span>
                        </span>
                        <span className="text-muted-foreground truncate text-xs">
                          {description}
                        </span>
                        <span className="text-muted-foreground/70 truncate text-[10px]">
                          {[server.transport, server.catalogId || 'custom']
                            .filter(Boolean)
                            .join(' · ')}
                        </span>
                      </button>
                    )
                  }

                  const { skill } = item
                  const description =
                    cleanSkillDescription(skill.description) || skill.name
                  const iconSource = composerSkillIcon(skill)
                  return (
                    <button
                      key={item.key}
                      type="button"
                      tabIndex={-1}
                      role="option"
                      aria-selected={isSelected}
                      ref={node => {
                        if (node) slashItemRefs.current.set(item.key, node)
                        else slashItemRefs.current.delete(item.key)
                      }}
                      onMouseDown={event => event.preventDefault()}
                      onMouseEnter={() => setSelectedSlashKey(item.key)}
                      onClick={() => {
                        onPickSkill(skill)
                      }}
                      className={cn(
                        'hover:bg-muted flex w-full flex-col rounded-md px-2 py-1.5 text-left',
                        isSelected && 'bg-muted'
                      )}
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        {iconSource ? (
                          <img
                            src={iconSource}
                            alt=""
                            className={cn(
                              'size-[18px] shrink-0 rounded object-contain',
                              skillIconInvertInDark(skill) && 'dark:invert'
                            )}
                          />
                        ) : (
                          <span className="bg-primary/10 text-primary inline-flex size-[18px] shrink-0 items-center justify-center rounded">
                            <Sparkles className="size-3" />
                          </span>
                        )}
                        <span className="truncate text-sm font-medium">
                          {skill.name}
                        </span>
                      </span>
                      <span className="text-muted-foreground truncate text-xs">
                        {description}
                      </span>
                      {(skill.author || skill.version) && (
                        <span className="text-muted-foreground/70 truncate text-[10px]">
                          {[skill.author, skill.version]
                            .filter(Boolean)
                            .join(' · ')}
                        </span>
                      )}
                    </button>
                  )
                })
              ) : (
                <div className="text-muted-foreground px-2 py-1.5 text-xs">
                  {selectedSpecialist
                    ? `No matching skills or MCPs for ${selectedSpecialist.name}`
                    : 'No skills or MCPs found'}
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
        <ScrollArea className="h-72">
          <div className="px-1 py-1">
            {selectedMcp ? (
              <div className="space-y-3 px-2 py-1">
                <div className="flex items-start justify-between gap-2">
                  <span className="truncate text-sm font-semibold">
                    {selectedMcp.name}
                  </span>
                  <a
                    href={
                      selectedMcp.catalogId
                        ? `/dashboard/mcp/catalog/${encodeURIComponent(
                            selectedMcp.catalogId
                          )}`
                        : `/dashboard/mcp/server/${encodeURIComponent(
                            selectedMcp.id
                          )}`
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary shrink-0 text-[11px] font-medium hover:underline"
                    onMouseDown={event => event.preventDefault()}
                  >
                    Read more
                  </a>
                </div>
                <p className="text-muted-foreground line-clamp-5 text-[11px] leading-relaxed">
                  {previewOverview ||
                    `Mention mcp:${selectedMcp.name} so the agent prefers tools from this MCP server.`}
                </p>
                <div className="border-border/60 border-t pt-2">
                  <p className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase tracking-wide">
                    Insert
                  </p>
                  <button
                    type="button"
                    tabIndex={-1}
                    onMouseDown={event => event.preventDefault()}
                    onClick={() => onPickMcp(selectedMcp)}
                    className="hover:bg-muted/50 border-border/60 bg-background w-full rounded-md border px-2 py-1.5 text-left"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="block truncate text-[11px] font-medium">
                        Mention this MCP
                      </span>
                      <span className="border-primary/30 text-primary inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium">
                        Insert
                        <CornerDownLeft className="h-3 w-3" />
                      </span>
                    </span>
                    <span className="text-muted-foreground mt-0.5 line-clamp-2 block text-[10px]">
                      Adds mcp:{selectedMcp.name} so the agent can prioritize
                      its tools.
                    </span>
                  </button>
                </div>
              </div>
            ) : selectedSkill ? (
              <div className="space-y-3 px-2 py-1">
                <div className="flex items-start justify-between gap-2">
                  <span className="truncate text-sm font-semibold">
                    {selectedSkill.name}
                  </span>
                  <a
                    href={`/dashboard/skills/${encodeURIComponent(
                      selectedSkill.name
                    )}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary shrink-0 text-[11px] font-medium hover:underline"
                    onMouseDown={event => event.preventDefault()}
                  >
                    Read more
                  </a>
                </div>
                <p className="text-muted-foreground line-clamp-3 text-[11px] leading-relaxed">
                  {previewLoading
                    ? 'Loading preview…'
                    : previewOverview ||
                      cleanSkillDescription(selectedSkill.description) ||
                      `Use /${selectedSkill.name} to run this skill.`}
                </p>
                <div className="border-border/60 border-t pt-2">
                  <p className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase tracking-wide">
                    Examples
                  </p>
                  <div className="space-y-1">
                    {selectedExamples.map(example => (
                      <button
                        key={`${selectedSkill.name}-${example.title}`}
                        type="button"
                        tabIndex={-1}
                        onMouseDown={event => event.preventDefault()}
                        onClick={() =>
                          onPickExample(selectedSkill.name, example.prompt)
                        }
                        className="hover:bg-muted/50 border-border/60 bg-background w-full rounded-md border px-2 py-1.5 text-left"
                      >
                        <span className="flex items-center justify-between gap-2">
                          <span className="block truncate text-[11px] font-medium">
                            {example.title}
                          </span>
                          <span className="border-primary/30 text-primary inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium">
                            Try
                            <CornerDownLeft className="h-3 w-3" />
                          </span>
                        </span>
                        <span className="text-muted-foreground mt-0.5 line-clamp-2 block text-[10px]">
                          {example.prompt}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground p-3 text-xs">
                Select a skill or MCP to preview.
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
})
