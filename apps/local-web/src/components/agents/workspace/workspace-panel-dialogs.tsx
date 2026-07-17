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
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
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
  isDirectory = false,
  onClose,
  onConfirm
}: {
  path: string | null
  busy: boolean
  isDirectory?: boolean
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
          <DialogTitle>
            {isDirectory ? 'Delete folder' : 'Delete file'}
          </DialogTitle>
          <DialogDescription>
            Permanently delete{' '}
            <span className="text-foreground font-medium">
              {path?.split('/').at(-1) || path}
            </span>
            {isDirectory ? ' and everything inside it' : ''} from this session
            workspace? This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
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

export function WorkspaceRenameDialog({
  path,
  value,
  busy,
  onValueChange,
  onClose,
  onSubmit
}: {
  path: string | null
  value: string
  busy: boolean
  onValueChange: (value: string) => void
  onClose: () => void
  onSubmit: () => void
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
          <DialogTitle>Rename</DialogTitle>
          <DialogDescription>
            Enter a new name for{' '}
            <span className="text-foreground font-medium">
              {path?.split('/').at(-1) || path}
            </span>
            .
          </DialogDescription>
        </DialogHeader>
        <Input
          value={value}
          onChange={event => onValueChange(event.target.value)}
          autoFocus
          onKeyDown={event => {
            if (event.key === 'Enter' && value.trim() && !busy) {
              event.preventDefault()
              onSubmit()
            }
          }}
        />
        <DialogFooter>
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={!value.trim() || busy}
            onClick={onSubmit}
          >
            {busy ? 'Renaming…' : 'Rename'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function WorkspaceMoveFileDialog({
  sourcePath,
  folders,
  busy,
  onClose,
  onSubmit
}: {
  sourcePath: string | null
  folders: string[]
  busy: boolean
  onClose: () => void
  onSubmit: (targetFolder: string) => void
}) {
  const sourceName = sourcePath?.split('/').at(-1) || sourcePath || ''
  const sourceDir =
    sourcePath && sourcePath.includes('/')
      ? sourcePath.slice(0, sourcePath.lastIndexOf('/'))
      : ''

  return (
    <Dialog
      open={Boolean(sourcePath)}
      onOpenChange={open => {
        if (!open) onClose()
      }}
    >
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Move to folder</DialogTitle>
          <DialogDescription>
            Choose a destination for{' '}
            <span className="text-foreground font-medium">{sourceName}</span>.
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-56 space-y-0.5 overflow-y-auto">
          <button
            type="button"
            disabled={busy || sourceDir === ''}
            className="hover:bg-muted flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm disabled:opacity-40"
            onClick={() => onSubmit('')}
          >
            Workspace root
          </button>
          {folders.map(folder => (
            <button
              key={folder}
              type="button"
              disabled={
                busy ||
                folder === sourcePath ||
                folder === sourceDir ||
                Boolean(sourcePath?.startsWith(`${folder}/`))
              }
              className="hover:bg-muted flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm disabled:opacity-40"
              onClick={() => onSubmit(folder)}
            >
              {folder}
            </button>
          ))}
          {folders.length === 0 ? (
            <p className="text-muted-foreground px-2 py-2 text-xs">
              No folders yet. Create one with New folder…
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
