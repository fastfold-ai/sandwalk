import Editor from '@monaco-editor/react'
import type { McpJsonDocument } from '@sandwalk/agent-ui-core'
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
  const dark = resolveDark()

  useEffect(() => {
    if (!open) return
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
      <DialogContent className="bg-card text-card-foreground border-border flex max-h-[min(90vh,44rem)] max-w-3xl flex-col gap-0 overflow-hidden rounded-2xl p-0 shadow-xl sm:rounded-2xl">
        <DialogHeader className="space-y-1.5 px-6 pt-6 pb-3 text-left">
          <DialogTitle>Edit mcp.json</DialogTitle>
          <DialogDescription>
            MCP config
            {path ? (
              <>
                {' '}
                · <span className="font-mono text-[11px]">{path}</span>
              </>
            ) : null}
            . Saving replaces custom (non-catalog) servers.
          </DialogDescription>
        </DialogHeader>

        <div className="border-border mx-6 mb-3 overflow-hidden rounded-xl border">
          {loading ? (
            <div className="text-muted-foreground grid h-[22rem] place-items-center text-sm">
              Loading…
            </div>
          ) : (
            <Editor
              height="22rem"
              language="json"
              theme={dark ? 'vs-dark' : 'light'}
              value={draft}
              onChange={value => setDraft(value ?? '')}
              options={{
                minimap: { enabled: false },
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
          <p className="text-destructive px-6 pb-2 text-sm">{error}</p>
        ) : null}

        <DialogFooter className="bg-muted/30 border-t px-6 py-4 sm:justify-end">
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
