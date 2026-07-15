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

export function WorkspacePathDialog({
  kind,
  value,
  busy,
  onValueChange,
  onClose,
  onSubmit
}: {
  kind: 'file' | 'folder' | null
  value: string
  busy: boolean
  onValueChange: (value: string) => void
  onClose: () => void
  onSubmit: () => void
}) {
  return (
    <Dialog
      open={Boolean(kind)}
      onOpenChange={open => {
        if (!open) onClose()
      }}
    >
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>
            {kind === 'folder' ? 'New folder' : 'New file'}
          </DialogTitle>
          <DialogDescription>
            {kind === 'folder'
              ? 'Enter a relative folder path in this session workspace.'
              : 'Enter a relative file path in this session workspace.'}
          </DialogDescription>
        </DialogHeader>
        <Input
          value={value}
          onChange={event => onValueChange(event.target.value)}
          placeholder={
            kind === 'folder' ? 'results/run-1' : 'notes/summary.md'
          }
          autoFocus
          onKeyDown={event => {
            if (event.key === 'Enter' && value.trim() && !busy) {
              event.preventDefault()
              onSubmit()
            }
          }}
        />
        <DialogFooter>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            disabled={!value.trim() || busy}
            onClick={onSubmit}
          >
            {busy ? 'Creating…' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function WorkspaceDeleteFileDialog({
  path,
  busy,
  onClose,
  onConfirm
}: {
  path: string | null
  busy: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  return (
    <Dialog
      open={Boolean(path)}
      onOpenChange={open => {
        if (!open) onClose()
      }}
    >
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Delete file</DialogTitle>
          <DialogDescription>
            Permanently delete{' '}
            <span className="text-foreground font-medium">
              {path?.split('/').at(-1) || path}
            </span>{' '}
            from this session workspace? This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            variant="destructive"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
