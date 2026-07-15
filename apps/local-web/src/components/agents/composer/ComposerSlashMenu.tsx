import type {
  AgentSkill,
  AgentSkillDetail,
  McpServer,
  Specialist
} from '@sandwalk/agent-ui-core'
import {
  forwardRef,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState
} from 'react'

import {
  buildSlashResults,
  cleanSkillDescription,
  type SlashItem
} from '@/components/agents/composer/composer-mention-utils'
import { ComposerSlashList } from '@/components/agents/composer/ComposerSlashList'
import { ComposerSlashPreview } from '@/components/agents/composer/ComposerSlashPreview'
import {
  extractSkillOverviewFromMarkdown,
  getSkillPromptExamples
} from '@/components/agents/skill-examples'

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
  }, [onLoadSkill, selectedMcpId, selectedSkillName, open])

  useEffect(() => {
    if (!open || !selectedMcpId || !selectedMcp) return
    const overview =
      String(selectedMcp.description || '').trim() ||
      `Mention mcp:${selectedMcp.name} so the agent prefers tools from this MCP server.`
    setPreviewLoading(false)
    setPreviewOverview(current => (current === overview ? current : overview))
  }, [selectedMcpId, open, selectedMcp])

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
        <ComposerSlashList
          slashResults={slashResults}
          selectedSlashKey={selectedSlashKey}
          selectedSpecialist={selectedSpecialist}
          listRootRef={listRootRef}
          slashItemRefs={slashItemRefs}
          onSelectKey={setSelectedSlashKey}
          onPickSkill={onPickSkill}
          onPickMcp={onPickMcp}
        />
        <ComposerSlashPreview
          selectedMcp={selectedMcp}
          selectedSkill={selectedSkill}
          previewLoading={previewLoading}
          previewOverview={previewOverview}
          selectedExamples={selectedExamples}
          onPickMcp={onPickMcp}
          onPickExample={onPickExample}
        />
      </div>
    </div>
  )
})
