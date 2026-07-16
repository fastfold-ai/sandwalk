import Editor from '@monaco-editor/react'
import type { WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import { Code2, Eye, ListChecks } from 'lucide-react'
import { useRef, useState } from 'react'

import { planModeAccent } from '@/components/agents/composer/ComposerModeMenu'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { MarkdownContent } from './MarkdownContent'
import { StructureViewer } from './StructureViewer'
import {
  fileTextContent,
  isMarkdown,
  isPlansMarkdown,
  isSpreadsheet,
  isStructure,
  isSvg,
  isTextLike,
  languageFor
} from './workspace-utils'

function TablePreview({ content, path }: { content: string; path: string }) {
  const separator = path.toLowerCase().endsWith('.tsv') ? '\t' : ','
  const rows = content
    .split(/\r?\n/)
    .filter(Boolean)
    .map(line => line.split(separator))
  if (rows.length === 0) {
    return (
      <div className="text-muted-foreground grid h-full place-items-center text-sm">
        Empty file
      </div>
    )
  }
  return (
    <div className="h-full overflow-auto">
      <table className="min-w-full border-collapse text-[11px]">
        <thead className="bg-muted sticky top-0">
          <tr>
            {rows[0].map((cell, index) => (
              <th
                key={`${cell}-${index}`}
                className="border px-2 py-1.5 text-left font-medium"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(1, 1000).map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className="whitespace-nowrap border px-2 py-1.5"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MarkdownFilePreview({
  path,
  text,
  editable,
  draft,
  editorDark,
  onDraftChange,
  onSave,
  onBuildPlan
}: {
  path: string
  text: string
  editable: boolean
  draft: string
  editorDark: boolean
  onDraftChange: (value: string) => void
  onSave?: () => void
  onBuildPlan?: (path: string) => void
}) {
  const [mode, setMode] = useState<'preview' | 'code'>('preview')
  const onSaveRef = useRef(onSave)
  onSaveRef.current = onSave
  const source = editable ? draft : text
  const showBuild = Boolean(onBuildPlan && isPlansMarkdown(path))

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-end gap-1 border-b px-2 py-1">
        <div className="bg-muted/60 inline-flex rounded-md p-0.5">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={cn(
              'h-6 gap-1 rounded-sm px-2 text-[11px]',
              mode === 'preview' && 'bg-background shadow-sm'
            )}
            onClick={() => setMode('preview')}
          >
            <Eye className="size-3" />
            Preview
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={cn(
              'h-6 gap-1 rounded-sm px-2 text-[11px]',
              mode === 'code' && 'bg-background shadow-sm'
            )}
            onClick={() => setMode('code')}
          >
            <Code2 className="size-3" />
            Code
          </Button>
          {showBuild ? (
            <Button
              type="button"
              size="sm"
              className={cn(
                'h-6 gap-1 rounded-sm px-2 text-[11px] shadow-none',
                planModeAccent.send
              )}
              onClick={() => onBuildPlan?.(path)}
            >
              <ListChecks className="size-3" />
              Build
            </Button>
          ) : null}
        </div>
      </div>
      {mode === 'preview' ? (
        <div className="min-h-0 flex-1 overflow-auto px-4 py-4">
          <MarkdownContent
            content={source}
            className="max-w-none text-sm [&_h1]:mb-3 [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:text-base [&_h2]:font-semibold [&_h3]:mb-1.5 [&_h3]:mt-4 [&_h3]:text-sm [&_h3]:font-semibold [&_li]:my-0.5 [&_ol]:my-2 [&_p]:my-2 [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto [&_ul]:my-2"
          />
        </div>
      ) : (
        <div className="min-h-0 flex-1">
          <Editor
            height="100%"
            value={source}
            onChange={editable ? value => onDraftChange(value || '') : undefined}
            language="markdown"
            theme={editorDark ? 'vs-dark' : 'vs'}
            onMount={(editor, monaco) => {
              if (!editable) return
              editor.addCommand(
                monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
                () => {
                  onSaveRef.current?.()
                }
              )
            }}
            options={{
              readOnly: !editable,
              minimap: { enabled: false },
              fontSize: 12,
              lineNumbers: 'on',
              lineNumbersMinChars: 3,
              wordWrap: 'on',
              padding: { top: 12 },
              scrollBeyondLastLine: false,
              automaticLayout: true
            }}
          />
        </div>
      )}
    </div>
  )
}

export function FilePreview({
  active,
  draft,
  editorDark,
  onDraftChange,
  onSave,
  onBuildPlan
}: {
  active: WorkspaceFileContent
  draft: string
  editorDark: boolean
  onDraftChange: (value: string) => void
  onSave?: () => void
  onBuildPlan?: (path: string) => void
}) {
  const text = fileTextContent(active, draft)
  const editable = active.encoding === 'text'
  const onSaveRef = useRef(onSave)
  onSaveRef.current = onSave

  if (isStructure(active.path)) {
    return (
      <StructureViewer
        data={text}
        format={
          active.path.toLowerCase().endsWith('.pdb')
            ? 'pdb'
            : active.path.toLowerCase().endsWith('.sdf')
              ? 'sdf'
              : 'cif'
        }
      />
    )
  }
  if (isSvg(active.path) || active.mimeType === 'image/svg+xml') {
    const src =
      active.encoding === 'base64'
        ? `data:image/svg+xml;base64,${active.content}`
        : `data:image/svg+xml;charset=utf-8,${encodeURIComponent(text)}`
    return (
      <div className="bg-muted/10 grid h-full place-items-center overflow-auto p-4">
        <img
          src={src}
          alt={active.path}
          className="max-h-full max-w-full object-contain"
        />
      </div>
    )
  }
  if (isSpreadsheet(active.path)) {
    return <TablePreview content={text} path={active.path} />
  }
  if (isMarkdown(active.path) && (editable || isTextLike(active.path))) {
    return (
      <MarkdownFilePreview
        key={active.path}
        path={active.path}
        text={text}
        editable={editable}
        draft={draft}
        editorDark={editorDark}
        onDraftChange={onDraftChange}
        onSave={onSave}
        onBuildPlan={onBuildPlan}
      />
    )
  }
  if (editable || isTextLike(active.path)) {
    return (
      <div className="h-full min-h-0 w-full">
        <Editor
          height="100%"
          value={editable ? draft : text}
          onChange={editable ? value => onDraftChange(value || '') : undefined}
          language={languageFor(active.path)}
          theme={editorDark ? 'vs-dark' : 'vs'}
          onMount={(editor, monaco) => {
            if (!editable) return
            editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
              onSaveRef.current?.()
            })
          }}
          options={{
            readOnly: !editable,
            minimap: { enabled: false },
            fontSize: 12,
            lineNumbers: 'on',
            lineNumbersMinChars: 3,
            wordWrap: 'on',
            padding: { top: 12 },
            scrollBeyondLastLine: false,
            automaticLayout: true
          }}
        />
      </div>
    )
  }
  if (active.mimeType === 'application/pdf') {
    return (
      <iframe
        title={active.path}
        src={`data:application/pdf;base64,${active.content}`}
        className="h-full w-full border-0"
      />
    )
  }
  if (active.mimeType.startsWith('image/')) {
    return (
      <div className="bg-muted/10 grid h-full place-items-center p-4">
        <img
          src={`data:${active.mimeType};base64,${active.content}`}
          alt={active.path}
          className="max-h-full max-w-full object-contain"
        />
      </div>
    )
  }
  return (
    <div className="text-muted-foreground grid h-full place-items-center text-sm">
      Binary preview unavailable
    </div>
  )
}
