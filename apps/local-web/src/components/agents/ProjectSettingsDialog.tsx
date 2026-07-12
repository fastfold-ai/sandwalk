import type { AgentProject } from '@fastfold/agent-ui-core'
import { useEffect, useState } from 'react'

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
  }) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [agentContext, setAgentContext] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !project) return
    setName(project.name)
    setDescription(project.description || '')
    setAgentContext(project.agentContext || '')
    setBusy(false)
  }, [open, project])

  const submit = async () => {
    const trimmed = name.trim()
    if (!trimmed || busy || !project) return
    setBusy(true)
    try {
      await onSave({
        name: trimmed,
        description: description.trim(),
        agentContext: agentContext.trim()
      })
      onOpenChange(false)
    } catch {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg gap-0 p-0">
        <DialogHeader className="border-b px-5 py-4">
          <DialogTitle>Project Settings</DialogTitle>
          <DialogDescription className="sr-only">
            Edit project name, description, and agent context.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 px-5 py-4">
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Name</span>
            <Input
              value={name}
              onChange={event => setName(event.target.value)}
              placeholder="Project name"
              autoFocus
              maxLength={120}
              onKeyDown={event => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  void submit()
                }
              }}
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Description</span>
            <p className="text-muted-foreground text-xs">
              Shown in the project list for your reference — not included in the
              agent&apos;s prompt.
            </p>
            <textarea
              value={description}
              onChange={event => setDescription(event.target.value)}
              placeholder="Describe what this project is about..."
              rows={3}
              className="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring flex w-full rounded-md border px-3 py-2 text-sm outline-none focus-visible:ring-1"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Agent Context</span>
            <p className="text-muted-foreground text-xs">
              This context will be included in every agent&apos;s system prompt
              for this project. Use it to provide background information,
              conventions, or instructions that all agents should follow.
            </p>
            <textarea
              value={agentContext}
              onChange={event => setAgentContext(event.target.value)}
              placeholder="e.g., This project studies the effects of compound X on gene Y in cell line Z. Always use GRCh38 for genome references..."
              rows={5}
              className="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring flex w-full rounded-md border px-3 py-2 text-sm outline-none focus-visible:ring-1"
            />
          </label>
        </div>
        <DialogFooter className="border-t px-5 py-3">
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
