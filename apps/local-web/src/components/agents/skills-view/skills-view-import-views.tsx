import type { AgentSkillSource } from '@sandwalk/agent-ui-core'
import { GitBranch } from 'lucide-react'
import type { RefObject } from 'react'

import { CardGridSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  suggestionSourceIcon,
  suggestionSourceLabel
} from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

import { SkillsBreadcrumb } from './skills-view-shared'

export function SkillsImportGithubView({
  githubSource,
  onGithubSourceChange,
  installing,
  onBack,
  onSubmit
}: {
  githubSource: string
  onGithubSourceChange: (value: string) => void
  installing: boolean
  onBack: () => void
  onSubmit: () => void
}) {
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
        <SkillsBreadcrumb onBack={onBack} />
        <section className="bg-card mt-4 space-y-4 rounded-xl border p-6">
          <div>
            <h2 className="text-lg font-semibold">Import from GitHub</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Use owner/repo, owner/repo@path, or a GitHub URL. This matches how
              `sandwalk skills add` parses sources.
            </p>
          </div>
          <Input
            value={githubSource}
            onChange={event => onGithubSourceChange(event.target.value)}
            placeholder="fastfold-ai/skills@skills/fold"
            autoFocus
            onKeyDown={event => {
              if (event.key === 'Enter' && githubSource.trim() && !installing) {
                event.preventDefault()
                onSubmit()
              }
            }}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={onBack}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!githubSource.trim() || installing}
              onClick={onSubmit}
            >
              {installing ? 'Importing…' : 'Import'}
            </Button>
          </div>
        </section>
      </div>
    </ScrollArea>
  )
}

export function SkillsImportFileView({
  uploadFile,
  uploadInputRef,
  onUploadFileChange,
  installing,
  onBack,
  onSubmit
}: {
  uploadFile: File | null
  uploadInputRef: RefObject<HTMLInputElement | null>
  onUploadFileChange: (file: File | null) => void
  installing: boolean
  onBack: () => void
  onSubmit: () => void
}) {
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
        <SkillsBreadcrumb onBack={onBack} />
        <section className="bg-card mt-4 space-y-4 rounded-xl border p-6">
          <div>
            <h2 className="text-lg font-semibold">Import from file</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Choose a local .zip, .skill, or SKILL.md file.
            </p>
          </div>
          <Input
            ref={uploadInputRef}
            type="file"
            accept=".zip,.skill,.md"
            onChange={event => {
              const file = event.target.files?.[0] ?? null
              onUploadFileChange(file)
            }}
          />
          <p className="text-muted-foreground text-xs">
            {uploadFile
              ? `Selected: ${uploadFile.name}`
              : 'Pick a file to upload using your file browser.'}
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={onBack}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!uploadFile || installing}
              onClick={onSubmit}
            >
              {installing ? 'Uploading…' : 'Upload'}
            </Button>
          </div>
        </section>
      </div>
    </ScrollArea>
  )
}

export function SkillsTrustedSourcesView({
  trustedSources,
  trustedSelected,
  onTrustedSelectedChange,
  trustedLoading,
  selectedTrustedSources,
  installing,
  onBack,
  onSubmit
}: {
  trustedSources: AgentSkillSource[]
  trustedSelected: Record<string, boolean>
  onTrustedSelectedChange: (
    updater: (current: Record<string, boolean>) => Record<string, boolean>
  ) => void
  trustedLoading: boolean
  selectedTrustedSources: string[]
  installing: boolean
  onBack: () => void
  onSubmit: () => void
}) {
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-4xl px-6 py-8 md:px-10">
        <SkillsBreadcrumb onBack={onBack} />
        <section className="bg-card mt-4 space-y-4 rounded-xl border p-6">
          <div>
            <h2 className="text-lg font-semibold">Suggestions</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Suggested community skill collections from FastFold setup.
              Select one or more sources to install.
            </p>
          </div>
          {trustedLoading ? (
            <CardGridSkeleton cards={6} columns={3} />
          ) : trustedSources.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No suggestions are currently available.
            </p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {trustedSources.map(item => {
                const icon = suggestionSourceIcon(item)
                return (
                  <button
                    key={item.source}
                    type="button"
                    className={cn(
                      'bg-background/60 hover:bg-muted/40 flex items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                      trustedSelected[item.source] &&
                        'ring-primary bg-muted/40 ring-1'
                    )}
                    onClick={() =>
                      onTrustedSelectedChange(current => ({
                        ...current,
                        [item.source]: !current[item.source]
                      }))
                    }
                  >
                    {icon ? (
                      <img
                        src={icon}
                        alt=""
                        className="mt-0.5 size-8 shrink-0 rounded object-contain"
                      />
                    ) : (
                      <span className="bg-muted/30 text-muted-foreground mt-0.5 grid size-8 shrink-0 place-items-center rounded">
                        <GitBranch className="size-4" />
                      </span>
                    )}
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {suggestionSourceLabel(item)}
                      </p>
                      <p className="text-muted-foreground mt-0.5 text-xs">
                        {item.description}
                      </p>
                      <span className="text-muted-foreground mt-1 block truncate text-xs">
                        {item.source}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={onBack}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={selectedTrustedSources.length === 0 || installing}
              onClick={onSubmit}
            >
              {installing
                ? `Installing ${selectedTrustedSources.length}…`
                : `Install selected (${selectedTrustedSources.length})`}
            </Button>
          </div>
        </section>
      </div>
    </ScrollArea>
  )
}
