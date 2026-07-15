import type { AgentSkill, McpServer, Specialist } from '@sandwalk/agent-ui-core'
import { Plug, Sparkles } from 'lucide-react'
import { type MutableRefObject } from 'react'

import {
  cleanSkillDescription,
  mcpIconForServer,
  type SlashItem
} from '@/components/agents/composer/composer-mention-utils'
import { ScrollArea } from '@/components/ui/scroll-area'
import { composerSkillIcon, skillIconInvertInDark } from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

export function ComposerSlashList({
  slashResults,
  selectedSlashKey,
  selectedSpecialist,
  listRootRef,
  slashItemRefs,
  onSelectKey,
  onPickSkill,
  onPickMcp
}: {
  slashResults: SlashItem[]
  selectedSlashKey: string | null
  selectedSpecialist: Specialist | null
  listRootRef: MutableRefObject<HTMLDivElement | null>
  slashItemRefs: MutableRefObject<Map<string, HTMLButtonElement>>
  onSelectKey: (key: string) => void
  onPickSkill: (skill: AgentSkill) => void
  onPickMcp: (server: McpServer) => void
}) {
  const selectedSlashItem =
    slashResults.find(item => item.key === selectedSlashKey) ||
    slashResults[0] ||
    null

  return (
    <div ref={listRootRef} className="min-h-0 min-w-0">
      <ScrollArea className="border-border/60 h-72 border-r">
        <div className="p-1" role="listbox" aria-label="Skills and MCPs">
          {slashResults.length > 0 ? (
            slashResults.map(item => {
              const isSelected = selectedSlashItem?.key === item.key
              if (item.kind === 'mcp') {
                const { server } = item
                const description =
                  String(server.description || '').trim() || server.transport
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
                    onMouseEnter={() => onSelectKey(item.key)}
                    onClick={() => onPickMcp(server)}
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
                  onMouseEnter={() => onSelectKey(item.key)}
                  onClick={() => onPickSkill(skill)}
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
                      {[skill.author, skill.version].filter(Boolean).join(' · ')}
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
  )
}
