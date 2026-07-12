import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFile } from '@sandwalk/agent-ui-core'
import { Icon } from '@iconify/react'
import { useEffect, useState } from 'react'

import { getFileIcon } from '@/lib/file-icons'
import { cn } from '@/lib/utils'

import { StructureViewer } from './StructureViewer'

type ThumbKind = 'image' | 'structure' | 'text' | 'table' | 'icon'

function extensionOf(name: string) {
  const parts = name.toLowerCase().split('.')
  return parts.length > 1 ? parts.at(-1) || '' : ''
}

function classify(name: string): ThumbKind {
  const ext = extensionOf(name)
  if (
    ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'ico'].includes(ext)
  ) {
    return 'image'
  }
  if (['pdb', 'cif', 'mmcif', 'sdf'].includes(ext)) return 'structure'
  if (['csv', 'tsv'].includes(ext)) return 'table'
  if (
    [
      'json',
      'md',
      'txt',
      'yaml',
      'yml',
      'py',
      'ts',
      'tsx',
      'js',
      'jsx',
      'css',
      'html',
      'htm',
      'xml',
      'log'
    ].includes(ext)
  ) {
    return 'text'
  }
  return 'icon'
}

function structureFormat(name: string): 'pdb' | 'cif' | 'sdf' {
  const lower = name.toLowerCase()
  if (lower.endsWith('.pdb')) return 'pdb'
  if (lower.endsWith('.sdf')) return 'sdf'
  return 'cif'
}

function decodeContent(encoding: 'text' | 'base64', content: string) {
  if (encoding === 'text') return content
  try {
    return atob(content)
  } catch {
    return content
  }
}

function IconFallback({
  name,
  className
}: {
  name: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'text-muted-foreground grid h-full w-full place-items-center',
        className
      )}
    >
      <Icon icon={getFileIcon(name)} className="size-8 opacity-80" />
    </div>
  )
}

function ImageThumb({
  client,
  sessionId,
  path,
  name
}: {
  client: LocalAgentClient
  sessionId: string
  path: string
  name: string
}) {
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl: string | null = null
    void client
      .readFile(sessionId, path, controller.signal)
      .then(file => {
        if (controller.signal.aborted) return
        if (file.encoding === 'base64') {
          setSrc(
            `data:${file.mimeType || 'application/octet-stream'};base64,${
              file.content
            }`
          )
          return
        }
        const mime =
          file.mimeType && file.mimeType !== 'application/octet-stream'
            ? file.mimeType
            : name.toLowerCase().endsWith('.svg')
            ? 'image/svg+xml'
            : 'text/plain'
        objectUrl = URL.createObjectURL(
          new Blob([file.content], { type: mime })
        )
        setSrc(objectUrl)
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [client, name, path, sessionId])

  if (failed) return <IconFallback name={name} />
  if (!src) {
    return <div className="bg-muted/30 h-full w-full animate-pulse" />
  }
  return (
    <img
      src={src}
      alt={name}
      className="h-full w-full object-contain p-1.5"
      onError={() => setFailed(true)}
    />
  )
}

function TextThumb({
  client,
  sessionId,
  path,
  name
}: {
  client: LocalAgentClient
  sessionId: string
  path: string
  name: string
}) {
  const [lines, setLines] = useState<string[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void client
      .readFile(sessionId, path, controller.signal)
      .then(file => {
        if (controller.signal.aborted) return
        const text = decodeContent(file.encoding, file.content)
        setLines(text.replace(/\r\n/g, '\n').split('\n').slice(0, 10))
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => controller.abort()
  }, [client, path, sessionId])

  if (failed) return <IconFallback name={name} />
  if (!lines) {
    return <div className="bg-muted/30 h-full w-full animate-pulse" />
  }

  return (
    <pre className="text-muted-foreground h-full w-full overflow-hidden p-2 font-mono text-[9px] leading-[1.35]">
      {lines.join('\n')}
    </pre>
  )
}

function TableThumb({
  client,
  sessionId,
  path,
  name
}: {
  client: LocalAgentClient
  sessionId: string
  path: string
  name: string
}) {
  const [rows, setRows] = useState<string[][] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void client
      .readFile(sessionId, path, controller.signal)
      .then(file => {
        if (controller.signal.aborted) return
        const text = decodeContent(file.encoding, file.content)
        const separator = path.toLowerCase().endsWith('.tsv') ? '\t' : ','
        setRows(
          text
            .split(/\r?\n/)
            .filter(Boolean)
            .slice(0, 5)
            .map(line => line.split(separator).slice(0, 4))
        )
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => controller.abort()
  }, [client, path, sessionId])

  if (failed) return <IconFallback name={name} />
  if (!rows) {
    return <div className="bg-muted/30 h-full w-full animate-pulse" />
  }
  if (rows.length === 0) return <IconFallback name={name} />

  return (
    <div className="h-full w-full overflow-hidden p-1.5">
      <table className="w-full border-collapse text-[8px] leading-tight">
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className={rowIndex === 0 ? 'font-medium' : ''}>
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className="border-border/50 truncate border px-1 py-0.5"
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

function StructureThumb({
  client,
  sessionId,
  path,
  name
}: {
  client: LocalAgentClient
  sessionId: string
  path: string
  name: string
}) {
  const [data, setData] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void client
      .readFile(sessionId, path, controller.signal)
      .then(file => {
        if (controller.signal.aborted) return
        setData(decodeContent(file.encoding, file.content))
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => controller.abort()
  }, [client, path, sessionId])

  if (failed) return <IconFallback name={name} />
  if (!data) {
    return <div className="bg-muted/30 h-full w-full animate-pulse" />
  }

  return <StructureViewer data={data} format={structureFormat(name)} compact />
}

export function ArtifactGridThumb({
  client,
  sessionId,
  file
}: {
  client: LocalAgentClient
  sessionId: string
  file: WorkspaceFile
}) {
  const kind = classify(file.name)

  return (
    <div className="bg-muted/25 relative aspect-[4/3] w-full overflow-hidden rounded-md border border-transparent">
      {kind === 'icon' ? (
        <IconFallback name={file.name} />
      ) : kind === 'image' ? (
        <ImageThumb
          client={client}
          sessionId={sessionId}
          path={file.path}
          name={file.name}
        />
      ) : kind === 'structure' ? (
        <StructureThumb
          client={client}
          sessionId={sessionId}
          path={file.path}
          name={file.name}
        />
      ) : kind === 'table' ? (
        <TableThumb
          client={client}
          sessionId={sessionId}
          path={file.path}
          name={file.name}
        />
      ) : (
        <TextThumb
          client={client}
          sessionId={sessionId}
          path={file.path}
          name={file.name}
        />
      )}
    </div>
  )
}
