import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useEffect, useMemo, useState } from 'react'

import { getFileIcon } from '@/lib/file-icons'
import { mediaObjectUrlFromFile } from '@/lib/media-src'
import { cn } from '@/lib/utils'

import { AudioPlayPreview } from './AudioPlayPreview'
import { PdfFirstPagePreview } from './PdfFirstPagePreview'
import { VideoPlayPreview } from './VideoPlayPreview'
import { decodeContent, structureFormat } from './artifact-grid-thumb-utils'
import { Py2dMolMiniPreview } from './py2dmol/Py2dMolMiniPreview'

export function IconFallback({
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

export function ImageThumb({
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
  const isSvg = name.toLowerCase().endsWith('.svg')

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl: string | null = null
    setFailed(false)
    setSrc(null)
    void client
      .readFile(sessionId, path, controller.signal)
      .then(file => {
        if (controller.signal.aborted) return
        if (file.encoding === 'base64') {
          const mime =
            file.mimeType && file.mimeType !== 'application/octet-stream'
              ? file.mimeType
              : isSvg
                ? 'image/svg+xml'
                : 'application/octet-stream'
          setSrc(`data:${mime};base64,${file.content}`)
          return
        }
        // Match FilePreview: data URLs are more reliable for SVG than Blobs
        // (Blob + revoke races under Strict Mode leave empty dark tiles).
        if (isSvg || file.mimeType === 'image/svg+xml') {
          setSrc(
            `data:image/svg+xml;charset=utf-8,${encodeURIComponent(file.content)}`
          )
          return
        }
        const mime =
          file.mimeType && file.mimeType !== 'application/octet-stream'
            ? file.mimeType
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
  }, [client, isSvg, name, path, sessionId])

  if (failed) return <IconFallback name={name} />
  if (!src) {
    return <div className="bg-muted/30 h-full w-full animate-pulse" />
  }
  return (
    <div
      className={cn(
        'flex h-full w-full items-center justify-center',
        // Light plate so dark/currentColor SVGs stay visible in dark UI.
        isSvg && 'bg-white'
      )}
    >
      <img
        src={src}
        alt={name}
        className="h-full w-full object-contain p-1.5"
        onError={() => setFailed(true)}
      />
    </div>
  )
}

export function VideoThumb({
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
        objectUrl = mediaObjectUrlFromFile({ ...file, name })
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
    <VideoPlayPreview
      src={src}
      mode="thumb"
      muted
      interactive={false}
      onError={() => setFailed(true)}
    />
  )
}

export function AudioThumb({
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
        objectUrl = mediaObjectUrlFromFile({ ...file, name })
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
    <AudioPlayPreview
      src={src}
      title={name}
      mode="thumb"
      onError={() => setFailed(true)}
    />
  )
}

export function TextThumb({
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

export function PdfThumb({
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
  const [base64, setBase64] = useState<string | null>(null)
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl: string | null = null
    setFailed(false)
    setBase64(null)
    setUrl(null)
    void client
      .readFile(sessionId, path, controller.signal)
      .then(file => {
        if (controller.signal.aborted) return
        if (file.encoding === 'base64') {
          setBase64(file.content)
          return
        }
        objectUrl = URL.createObjectURL(
          new Blob([file.content], { type: 'application/pdf' })
        )
        setUrl(objectUrl)
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [client, path, sessionId])

  if (failed) return <IconFallback name={name} />
  if (!base64 && !url) {
    return <div className="bg-muted/30 h-full w-full animate-pulse" />
  }
  return (
    <div className="bg-white h-full w-full overflow-hidden">
      <PdfFirstPagePreview
        title={name}
        base64={base64}
        url={url}
        zoom={1.2}
        onError={() => setFailed(true)}
      />
    </div>
  )
}

export function StructureThumb({
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
  const [text, setText] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const structureKind = structureFormat(name)
  const format: 'pdb' | 'cif' | null =
    structureKind === 'pdb' ? 'pdb' : structureKind === 'sdf' ? null : 'cif'
  const viewerId = useMemo(
    () => `thumb-${path.replace(/[^a-zA-Z0-9_-]+/g, '_')}`,
    [path]
  )

  useEffect(() => {
    if (!format) return
    const controller = new AbortController()
    setFailed(false)
    setText(null)
    void client
      .readFile(sessionId, path, controller.signal)
      .then(file => {
        if (controller.signal.aborted) return
        setText(decodeContent(file.encoding, file.content))
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => controller.abort()
  }, [client, format, path, sessionId])

  if (!format || failed) return <IconFallback name={name} />
  if (!text) {
    return <div className="bg-muted/30 h-full w-full animate-pulse" />
  }
  return (
    <Py2dMolMiniPreview text={text} format={format} viewerId={viewerId} />
  )
}

export function TableThumb({
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

