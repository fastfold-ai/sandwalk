import { Check, ChevronDown, GitBranch, Plus, Search, Upload } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export function SkillsMainListToolbar({
  query,
  catalogSearchMode,
  catalogSearchEnabled,
  onQueryChange,
  onCatalogSearchModeChange,
  onEnableCatalogSearchMode,
  onOpenImportGithub,
  onOpenImportFile,
  onOpenTrustedSources
}: {
  query: string
  catalogSearchMode: boolean
  catalogSearchEnabled: boolean
  onQueryChange: (value: string) => void
  onCatalogSearchModeChange: (enabled: boolean) => void
  onEnableCatalogSearchMode: () => void
  onOpenImportGithub: () => void
  onOpenImportFile: () => void
  onOpenTrustedSources: () => void
}) {
  return (
    <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
      <div className="relative min-w-[280px] flex-1 max-w-3xl">
        <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
        <Input
          value={query}
          onChange={event => onQueryChange(event.target.value)}
          placeholder={
            catalogSearchMode
              ? 'Search skills.sh...'
              : 'Search skills, descriptions...'
          }
          className="border-border/70 bg-background/70 h-11 pl-10 pr-[9.5rem]"
        />
        <button
          type="button"
          className={cn(
            'absolute right-1.5 top-1/2 flex h-8 -translate-y-1/2 items-center gap-1.5 rounded-md px-2 text-xs transition-colors',
            catalogSearchMode
              ? 'bg-muted text-foreground'
              : 'text-muted-foreground hover:text-foreground',
            !catalogSearchEnabled && 'opacity-70'
          )}
          onClick={() => {
            if (catalogSearchMode) {
              onCatalogSearchModeChange(false)
              return
            }
            onEnableCatalogSearchMode()
          }}
          title={
            catalogSearchEnabled
              ? 'Toggle Skills.sh search'
              : 'Skills.sh needs setup'
          }
        >
          <img
            src="/suggestions/skills-sh.png"
            alt=""
            className="size-3.5 rounded object-contain dark:invert"
          />
          <span>Skills.sh</span>
          <span
            className={cn(
              'ml-0.5 inline-flex h-4 w-7 items-center rounded-full px-0.5 transition-colors',
              catalogSearchMode ? 'bg-foreground/80' : 'bg-muted-foreground/30'
            )}
            aria-hidden
          >
            <span
              className={cn(
                'bg-background size-3 rounded-full transition-transform',
                catalogSearchMode ? 'translate-x-3' : 'translate-x-0'
              )}
            />
          </span>
        </button>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-10">
            <Plus className="mr-1 size-3.5" />
            Add skill
            <ChevronDown className="ml-1 size-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={onOpenImportGithub}>
            <GitBranch className="size-4" />
            Import from GitHub
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onOpenImportFile}>
            <Upload className="size-4" />
            Upload from file
          </DropdownMenuItem>
          <DropdownMenuItem
            className={cn(
              !catalogSearchEnabled &&
                'text-muted-foreground/80 data-[highlighted]:text-muted-foreground/80'
            )}
            onClick={onEnableCatalogSearchMode}
          >
            <img
              src="/suggestions/skills-sh.png"
              alt=""
              className={cn(
                'size-4 rounded object-contain dark:invert',
                !catalogSearchEnabled && 'opacity-60'
              )}
            />
            <span>Search in Skills.sh</span>
            {!catalogSearchEnabled ? (
              <span className="text-muted-foreground/80 text-[11px]">
                (Needs setup)
              </span>
            ) : null}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onOpenTrustedSources}>
            <Check className="size-4" />
            Suggestions
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
