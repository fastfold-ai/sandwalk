import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import {
  DEFAULT_PROJECT_COLOR,
  DEFAULT_PROJECT_ICON
} from '@/lib/project-appearance'
import { cn } from '@/lib/utils'

import { ProjectAppearancePicker } from './ProjectAppearancePicker'
import { ProjectFolderField } from './ProjectFolderField'

const PROJECT_DIALOG_OVERLAY =
  'bg-black/10 data-[state=open]:backdrop-blur-none'
const PROJECT_DIALOG_CONTENT =
  'border-0 shadow-[0_18px_50px_-20px_rgba(0,0,0,0.35)] sm:rounded-2xl'

export function NewProjectDialog({
  open,
  onOpenChange,
  onCreate
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (input: {
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

  const reset = () => {
    setName('')
    setDescription('')
    setAgentContext('')
    setFolderPath('')
    setIcon(DEFAULT_PROJECT_ICON)
    setColor(DEFAULT_PROJECT_COLOR)
    setMoreOpen(false)
    setBusy(false)
  }

  const submit = async () => {
    const trimmed = name.trim()
    if (!trimmed || busy) return
    setBusy(true)
    try {
      await onCreate({
        name: trimmed,
        description: description.trim(),
        agentContext: agentContext.trim(),
        folderPath: folderPath.trim() || null,
        icon,
        color
      })
      reset()
      onOpenChange(false)
    } catch {
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={next => {
        if (!next) reset()
        onOpenChange(next)
      }}
    >
      <DialogContent
        overlayClassName={PROJECT_DIALOG_OVERLAY}
        className={cn('max-w-md gap-0 p-0', PROJECT_DIALOG_CONTENT)}
      >
        <DialogHeader className="px-5 pt-5 pb-1">
          <DialogTitle>Create project</DialogTitle>
          <DialogDescription className="sr-only">
            Create a project with an optional linked folder and shared agent
            context.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 px-5 py-4">
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
                    value={description}
                    onChange={event => setDescription(event.target.value)}
                    placeholder="Describe what this project is about..."
                    rows={3}
                    className="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring flex w-full rounded-md border px-3 py-2 text-sm outline-none focus-visible:ring-1"
                  />
                </label>
                <label className="block space-y-1.5">
                  <span className="text-sm font-medium">Agent Context</span>
                  <textarea
                    value={agentContext}
                    onChange={event => setAgentContext(event.target.value)}
                    placeholder="e.g., Always use GRCh38 for genome references..."
                    rows={4}
                    className="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring flex w-full rounded-md border px-3 py-2 text-sm outline-none focus-visible:ring-1"
                  />
                </label>
              </div>
            ) : null}
          </div>
        </div>
        <DialogFooter className="px-5 pb-5 pt-1">
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
            {busy ? 'Creating…' : 'Create project'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
