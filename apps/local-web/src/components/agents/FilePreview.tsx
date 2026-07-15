import Editor from '@monaco-editor/react'
import type { WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import { useRef } from 'react'

import { StructureViewer } from './StructureViewer'
import {
  fileTextContent,
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

export function FilePreview({
  active,
  draft,
  editorDark,
  onDraftChange,
  onSave
}: {
  active: WorkspaceFileContent
  draft: string
  editorDark: boolean
  onDraftChange: (value: string) => void
  onSave?: () => void
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
