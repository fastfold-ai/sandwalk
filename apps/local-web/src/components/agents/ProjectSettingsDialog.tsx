import type { AgentProject } from '@sandwalk/agent-ui-core'
import { ChevronDown } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  DEFAULT_PROJECT_COLOR,
  DEFAULT_PROJECT_ICON
} from '@/lib/project-appearance'
import { cn } from '@/lib/utils'

import { ProjectAppearancePicker } from './ProjectAppearancePicker'
import { ProjectFolderField } from './ProjectFolderField'

const PROJECT_DIALOG_OVERLAY =
  'bg-black/65 backdrop-blur-[2px] data-[state=open]:backdrop-blur-[2px]'
const PROJECT_DIALOG_CONTENT =
  'border-border/80 bg-popover ring-border/40 shadow-[0_24px_80px_-12px_rgba(0,0,0,0.75),0_0_0_1px_rgba(255,255,255,0.06)] ring-1 sm:rounded-2xl'

export function ProjectSettingsDialog({
  project,
  open,
  onOpenChange,
  onSave
}: {
  project: AgentProject | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (input: {
    name: string
    description: string
    agentContext: string
    folderPath: string | null
    icon: string
    color: string
  }) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [agentContext, setAgentContext] = useState('')
  const [folderPath, setFolderPath] = useState('')
  const [icon, setIcon] = useState(DEFAULT_PROJECT_ICON)
  const [color, setColor] = useState(DEFAULT_PROJECT_COLOR)
  const [moreOpen, setMoreOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const descriptionRef = useRef<HTMLTextAreaElement>(null)
  const agentContextRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!open || !project) return
    setName(project.name)
    setDescription(project.description || '')
    setAgentContext(project.agentContext || '')
    setFolderPath(project.folderPath || '')
    setIcon(project.icon || DEFAULT_PROJECT_ICON)
    setColor(project.color || DEFAULT_PROJECT_COLOR)
    setMoreOpen(Boolean(project.description || project.agentContext))
    setBusy(false)
  }, [open, project])

  useEffect(() => {
    if (!open || !moreOpen) return
    for (const el of [descriptionRef.current, agentContextRef.current]) {
      if (!el) continue
      el.style.height = '0px'
      el.style.height = `${el.scrollHeight}px`
    }
  }, [open, moreOpen, description, agentContext])

  const submit = async () => {
    const trimmed = name.trim()
    if (!trimmed || busy || !project) return
    setBusy(true)
    try {
      await onSave({
        name: trimmed,
        description: description.trim(),
        agentContext: agentContext.trim(),
        folderPath: folderPath.trim() || null,
        icon,
        color
      })
      onOpenChange(false)
    } catch {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        overlayClassName={PROJECT_DIALOG_OVERLAY}
        className={cn(
          'flex max-h-[min(90vh,44rem)] max-w-lg flex-col gap-0 overflow-hidden p-0',
          PROJECT_DIALOG_CONTENT
        )}
      >
        <DialogHeader className="shrink-0 px-5 pt-5 pb-1">
          <DialogTitle>Project Settings</DialogTitle>
          <DialogDescription className="sr-only">
            Edit project name, folder, appearance, and agent context.
          </DialogDescription>
        </DialogHeader>
        {/* Explicit height required — Radix ScrollArea does not scroll with max-h/flex alone. */}
        <ScrollArea className={moreOpen ? 'h-[min(55vh,28rem)]' : undefined}>
          <div className="space-y-4 px-5 py-4 pr-4">
            <div className="border-border flex items-center gap-2 rounded-lg border px-2 py-1.5">
              <ProjectAppearancePicker
                icon={icon}
                color={color}
                onChange={next => {
                  setIcon(next.icon)
                  setColor(next.color)
                }}
              />
              <input
                value={name}
                onChange={event => setName(event.target.value)}
                placeholder="Project name"
                autoFocus
                maxLength={120}
                className="placeholder:text-muted-foreground min-w-0 flex-1 bg-transparent text-sm outline-none"
                onKeyDown={event => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    void submit()
                  }
                }}
              />
            </div>

            <ProjectFolderField
              value={folderPath}
              onChange={setFolderPath}
              disabled={busy}
            />

            <div className="space-y-3">
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
                onClick={() => setMoreOpen(current => !current)}
              >
                More
                <ChevronDown
                  className={cn(
                    'size-3.5 transition-transform',
                    moreOpen && 'rotate-180'
                  )}
                />
              </button>
              {moreOpen ? (
                <div className="space-y-4">
                  <label className="block space-y-1.5">
                    <span className="text-sm font-medium">Description</span>
                    <textarea
                      ref={descriptionRef}
                      value={description}
                      onChange={event => setDescription(event.target.value)}
                      placeholder="Describe what this project is about..."
                      rows={3}
                      className="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring block min-h-24 w-full resize-none overflow-hidden rounded-md border px-3 py-2 font-mono text-xs leading-relaxed outline-none focus-visible:ring-1"
                    />
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-sm font-medium">Agent Context</span>
                    <textarea
                      ref={agentContextRef}
                      value={agentContext}
                      onChange={event => setAgentContext(event.target.value)}
                      placeholder="e.g., Always use GRCh38 for genome references..."
                      rows={3}
                      className="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring block min-h-20 w-full resize-none overflow-hidden rounded-md border px-3 py-2 text-sm outline-none focus-visible:ring-1"
                    />
                  </label>
                </div>
              ) : null}
            </div>
          </div>
        </ScrollArea>
        <DialogFooter className="shrink-0 px-5 pt-1 pb-5">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={() => void submit()}
            disabled={!name.trim() || busy}
          >
            {busy ? 'Saving…' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
