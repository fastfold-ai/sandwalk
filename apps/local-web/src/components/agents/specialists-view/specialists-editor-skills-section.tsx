import type { AgentSkill } from '@sandwalk/agent-ui-core'
import { ChevronDown, Search, Sparkles, X } from 'lucide-react'

import {
  SkillGlyph,
  skillMetaText
} from '@/components/agents/specialists-view/specialists-view-shared'
import { resolveSkillInstallSource } from '@/components/agents/specialists-view/specialists-view-utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

type SelectedSkillRow = {
  name: string
  skill: AgentSkill | null
  status: 'ok' | 'missing' | 'disabled'
  statusLabel: string | null
}

export function SpecialistsEditorSkillsSection({
  skillCount,
  onManageSkills,
  skillAddOpen,
  onSkillAddOpenChange,
  skillAddQuery,
  onSkillAddQueryChange,
  availableSkills,
  onAddSkill,
  selectedSkillRows,
  onOpenSkill,
  skillActionPending,
  onEnableSkill,
  onEnableSkillClick,
  onInstallSkillClick,
  onRemoveSkill
}: {
  skillCount: number
  onManageSkills?: () => void
  skillAddOpen: boolean
  onSkillAddOpenChange: (open: boolean) => void
  skillAddQuery: string
  onSkillAddQueryChange: (query: string) => void
  availableSkills: AgentSkill[]
  onAddSkill: (name: string) => void
  selectedSkillRows: SelectedSkillRow[]
  onOpenSkill?: (name: string) => void
  skillActionPending: string | null
  onEnableSkill?: (name: string) => Promise<void>
  onEnableSkillClick: (name: string) => void
  onInstallSkillClick: (name: string) => void
  onRemoveSkill: (name: string) => void
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-baseline gap-2">
          <h2 className="text-sm font-medium">Skills ({skillCount})</h2>
          {onManageSkills ? (
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground text-xs transition-colors"
              onClick={onManageSkills}
            >
              Manage all skills
            </button>
          ) : null}
        </div>
        <DropdownMenu
          open={skillAddOpen}
          onOpenChange={open => {
            onSkillAddOpenChange(open)
            if (!open) onSkillAddQueryChange('')
          }}
        >
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="bg-muted/40 hover:bg-muted/60 text-muted-foreground inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs transition-colors"
            >
              Add a skill…
              <ChevronDown className="size-3.5" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="w-80 p-0"
            onCloseAutoFocus={event => event.preventDefault()}
          >
            <div className="border-b px-2 py-2">
              <div className="relative">
                <Search className="text-muted-foreground/70 pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2" />
                <Input
                  value={skillAddQuery}
                  onChange={event => onSkillAddQueryChange(event.target.value)}
                  placeholder="Search"
                  className="h-8 border-0 bg-transparent pl-7 shadow-none focus-visible:ring-0"
                  autoFocus
                />
              </div>
            </div>
            <div className="chat-scrollbar max-h-56 overflow-y-auto py-1">
              {availableSkills.length === 0 ? (
                <p className="text-muted-foreground px-3 py-3 text-xs">
                  Nothing to add.
                </p>
              ) : (
                availableSkills.map(skill => {
                  const meta = skillMetaText(skill)
                  return (
                    <DropdownMenuItem
                      key={skill.name}
                      className="gap-2 py-2"
                      onClick={() => onAddSkill(skill.name)}
                    >
                      <SkillGlyph skill={skill} className="size-[18px]" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm">
                          {skill.name}
                        </span>
                        {skill.description ? (
                          <span className="text-muted-foreground block truncate text-xs">
                            {skill.description}
                          </span>
                        ) : null}
                        {meta ? (
                          <span className="text-muted-foreground/70 block truncate text-[10px]">
                            {meta}
                          </span>
                        ) : null}
                      </span>
                    </DropdownMenuItem>
                  )
                })
              )}
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {selectedSkillRows.length === 0 ? (
        <p className="text-muted-foreground py-2 text-sm">No skills selected.</p>
      ) : (
        <div className="divide-border/40 divide-y">
          {selectedSkillRows.map(row => {
            const meta = row.skill ? skillMetaText(row.skill) : null
            return (
              <div key={row.name} className="flex items-center gap-3 py-2.5">
                <button
                  type="button"
                  className={cn(
                    'flex min-w-0 flex-1 items-center gap-3 text-left',
                    onOpenSkill &&
                      'hover:opacity-90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded-md'
                  )}
                  disabled={!onOpenSkill}
                  onClick={() => onOpenSkill?.(row.name)}
                >
                  {row.skill ? (
                    <SkillGlyph skill={row.skill} />
                  ) : (
                    <span className="bg-muted flex size-7 shrink-0 items-center justify-center rounded-md">
                      <Sparkles className="text-muted-foreground size-3.5" />
                    </span>
                  )}
                  <span className="min-w-0 flex-1">
                    <span
                      className={cn(
                        'block truncate text-sm',
                        onOpenSkill && 'hover:underline'
                      )}
                    >
                      {row.name}
                    </span>
                    {meta || row.statusLabel ? (
                      <span className="text-muted-foreground block truncate text-xs">
                        {[meta, row.statusLabel].filter(Boolean).join(' · ')}
                      </span>
                    ) : null}
                  </span>
                </button>
                {row.status !== 'ok' ? (
                  <div className="flex shrink-0 items-center gap-1.5">
                    <span className="text-amber-500/90 text-[11px] font-medium">
                      {row.statusLabel}
                    </span>
                    {row.status === 'disabled' && onEnableSkill ? (
                      <button
                        type="button"
                        className="bg-muted/50 hover:bg-muted text-foreground rounded-full px-2 py-0.5 text-[11px] transition-colors"
                        disabled={skillActionPending === row.name}
                        onClick={() => onEnableSkillClick(row.name)}
                      >
                        {skillActionPending === row.name ? '…' : 'Enable'}
                      </button>
                    ) : null}
                    {row.status === 'missing' ? (
                      <button
                        type="button"
                        className="bg-muted/50 hover:bg-muted text-foreground rounded-full px-2 py-0.5 text-[11px] transition-colors"
                        disabled={skillActionPending === row.name}
                        onClick={() => onInstallSkillClick(row.name)}
                      >
                        {skillActionPending === row.name
                          ? '…'
                          : resolveSkillInstallSource(row.name)
                            ? 'Install'
                            : 'Find'}
                      </button>
                    ) : null}
                  </div>
                ) : null}
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground rounded-md p-1 transition-colors"
                  aria-label={`Remove ${row.name}`}
                  onClick={() => onRemoveSkill(row.name)}
                >
                  <X className="size-3.5" />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
