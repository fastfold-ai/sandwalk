import Editor from '@monaco-editor/react'
import type { McpJsonDocument } from '@sandwalk/agent-ui-core'
import { Maximize2, Minimize2 } from 'lucide-react'
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
import { resolveDark } from '@/lib/theme'
import { cn } from '@/lib/utils'

export function McpJsonEditorDialog({
  open,
  onOpenChange,
  onLoad,
  onSave
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onLoad: () => Promise<{ path: string; document: McpJsonDocument }>
  onSave: (document: McpJsonDocument) => Promise<void>
}) {
  const [path, setPath] = useState('')
  const [draft, setDraft] = useState('{\n  "mcpServers": {}\n}\n')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const dark = resolveDark()

  useEffect(() => {
    if (!open) {
      setExpanded(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    void onLoad()
      .then(result => {
        if (cancelled) return
        setPath(result.path)
        setDraft(`${JSON.stringify(result.document, null, 2)}\n`)
      })
      .catch(err => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [onLoad, open])

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const parsed = JSON.parse(draft) as McpJsonDocument
      if (!parsed || typeof parsed !== 'object' || !parsed.mcpServers) {
        throw new Error('JSON must include an "mcpServers" object.')
      }
      await onSave(parsed)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={next => {
        if (saving) return
        onOpenChange(next)
      }}
    >
      <DialogContent
        className={cn(
          'bg-card text-card-foreground border-border flex flex-col gap-0 overflow-hidden p-0 shadow-xl',
          expanded
            ? 'h-[100dvh] max-h-[100dvh] w-screen max-w-none translate-x-[-50%] translate-y-[-50%] rounded-none sm:rounded-none'
            : 'max-h-[min(90vh,44rem)] max-w-3xl rounded-2xl sm:rounded-2xl'
        )}
      >
        <button
          type="button"
          className="ring-offset-background focus:ring-ring text-muted-foreground absolute top-4 right-12 z-10 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-none"
          aria-label={expanded ? 'Exit full screen' : 'Expand to full screen'}
          onClick={() => setExpanded(current => !current)}
        >
          {expanded ? (
            <Minimize2 className="size-4" />
          ) : (
            <Maximize2 className="size-4" />
          )}
        </button>

        <DialogHeader className="shrink-0 space-y-1.5 px-6 pt-6 pr-20 pb-3 text-left">
          <DialogTitle>Edit mcp.json</DialogTitle>
          <DialogDescription>
            MCP config
            {path ? (
              <>
                {' '}
                · <span className="font-mono text-[11px]">{path}</span>
              </>
            ) : null}
            .
          </DialogDescription>
        </DialogHeader>

        <div
          className={cn(
            'border-border mx-6 mb-3 flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border',
            !expanded && 'h-[22rem] flex-none'
          )}
        >
          {loading ? (
            <div className="text-muted-foreground grid h-full min-h-[22rem] place-items-center text-sm">
              Loading…
            </div>
          ) : (
            <Editor
              height={expanded ? '100%' : '22rem'}
              language="json"
              theme={dark ? 'vs-dark' : 'light'}
              value={draft}
              onChange={value => setDraft(value ?? '')}
              options={{
                minimap: { enabled: expanded },
                fontSize: 12,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                wordWrap: 'on',
                automaticLayout: true,
                tabSize: 2
              }}
            />
          )}
        </div>

        {error ? (
          <p className="text-destructive shrink-0 px-6 pb-2 text-sm">{error}</p>
        ) : null}

        <DialogFooter className="bg-muted/30 shrink-0 border-t px-6 py-4 sm:justify-end">
          <Button
            type="button"
            variant="ghost"
            disabled={saving}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={loading || saving}
            onClick={() => void save()}
          >
            {saving ? 'Saving…' : 'Save MCPs'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
