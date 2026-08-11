import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { FileText } from 'lucide-react'
import { useEffect, useState } from 'react'

import { decodeContent } from '@/components/agents/artifact-grid-thumb-utils'
import { AudioPlayPreview } from '@/components/agents/AudioPlayPreview'
import { PdfFirstPagePreview } from '@/components/agents/PdfFirstPagePreview'
import { Py2dMolMiniPreview } from '@/components/agents/py2dmol/Py2dMolMiniPreview'
import { VideoPlayPreview } from '@/components/agents/VideoPlayPreview'
import { isStructure } from '@/components/agents/workspace-utils'
import { getFileIcon } from '@/lib/file-icons'
import { mediaObjectUrlFromFile } from '@/lib/media-src'
import { multimodalKindForFile } from '@/lib/multimodal-attach'
import { cn } from '@/lib/utils'

export type MessagePreviewKind =
  | 'image'
  | 'pdf'
  | 'video'
  | 'audio'
  | 'structure'

export function messageFilePreviewKind(path: string): MessagePreviewKind | null {
  const name = path.split('/').at(-1) || path
  if (isStructure(name)) return 'structure'
  const kind = multimodalKindForFile({ name })
  if (kind === 'image') return 'image'
  if (kind === 'video') return 'video'
  if (kind === 'audio') return 'audio'
  if (kind === 'file' && name.toLowerCase().endsWith('.pdf')) return 'pdf'
  return null
}

function FileChipFallback({
  path,
  onOpenFile
}: {
  path: string
  onOpenFile?: (path: string) => void
}) {
  const name = path.split('/').at(-1) || path
  const chipClass =
    'bg-card border-border/70 inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs'
  const body = (
    <>
      <Icon icon={getFileIcon(name)} className="size-3.5 shrink-0" />
      <span className="max-w-[220px] truncate">@{name}</span>
    </>
  )
  if (onOpenFile) {
    return (
      <button
        type="button"
        className={cn(chipClass, 'hover:bg-muted/40 cursor-pointer')}
        title={`Open @${path}`}
        onClick={() => onOpenFile(path)}
      >
        {body}
      </button>
    )
  }
  return (
    <span className={chipClass} title={`@${path}`}>
      {body}
    </span>
  )
}

export function MessageFilePreview({
  client,
  sessionId,
  path,
  onOpenFile
}: {
  client: LocalAgentClient
  sessionId: string
  path: string
  onOpenFile?: (path: string) => void
}) {
  const kind = messageFilePreviewKind(path)
  const name = path.split('/').at(-1) || path
  const [src, setSrc] = useState<string | null>(null)
  const [pdfBase64, setPdfBase64] = useState<string | null>(null)
  const [structureText, setStructureText] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!kind) return
    const controller = new AbortController()
    let objectUrl: string | null = null
    setSrc(null)
    setPdfBase64(null)
    setStructureText(null)
    setFailed(false)
    setLoaded(false)
    void client
      .readFile(sessionId, path, controller.signal)
      .then(file => {
        if (controller.signal.aborted) return
        if (kind === 'structure') {
          setStructureText(decodeContent(file.encoding, file.content))
          return
        }
        if (kind === 'pdf') {
          if (file.encoding === 'base64') {
            setPdfBase64(file.content)
            return
          }
          objectUrl = URL.createObjectURL(
            new Blob([file.content], { type: 'application/pdf' })
          )
          setSrc(objectUrl)
          return
        }
        if (kind === 'video' || kind === 'audio') {
          objectUrl = mediaObjectUrlFromFile({ ...file, name })
          setSrc(objectUrl)
          return
        }
        if (file.encoding === 'base64') {
          const mime = file.mimeType || 'application/octet-stream'
          setSrc(`data:${mime};base64,${file.content}`)
          return
        }
        const mime =
          file.mimeType && file.mimeType !== 'application/octet-stream'
            ? file.mimeType
            : 'application/octet-stream'
        objectUrl = URL.createObjectURL(new Blob([file.content], { type: mime }))
        setSrc(objectUrl)
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [client, kind, name, path, sessionId])

  if (!kind || failed) {
    return <FileChipFallback path={path} onOpenFile={onOpenFile} />
  }

  if (kind === 'structure') {
    const format = name.toLowerCase().endsWith('.pdb') ? 'pdb' : 'cif'
    const viewerId = `msg-${path.replace(/[^a-zA-Z0-9_-]+/g, '_')}`
    return (
      <div
        role={onOpenFile ? 'button' : undefined}
        tabIndex={onOpenFile ? 0 : undefined}
        className={cn(
          'bg-background/50 border-border/60 flex w-72 max-w-full flex-col overflow-hidden rounded-lg border text-left',
          onOpenFile ? 'hover:bg-background/80 cursor-pointer' : 'cursor-default'
        )}
        title={onOpenFile ? `Open @${path}` : `@${path}`}
        onClick={() => onOpenFile?.(path)}
        onKeyDown={event => {
          if (!onOpenFile) return
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onOpenFile(path)
          }
        }}
      >
        <div className="relative h-36 w-full overflow-hidden">
          {structureText ? (
            <Py2dMolMiniPreview
              text={structureText}
              format={format}
              viewerId={viewerId}
            />
          ) : (
            <div className="bg-muted/30 h-full w-full animate-pulse" />
          )}
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs">
          <Icon icon={getFileIcon(name)} className="size-3.5 shrink-0" />
          <span className="truncate">{name}</span>
        </div>
      </div>
    )
  }

  if (kind === 'pdf') {
    if (!pdfBase64 && !src) {
      return (
        <div
          className="bg-background/60 h-44 w-full max-w-[18rem] animate-pulse rounded-lg"
          aria-hidden
        />
      )
    }
    return (
      <div
        role={onOpenFile ? 'button' : undefined}
        tabIndex={onOpenFile ? 0 : undefined}
        className={cn(
          'bg-background/50 border-border/60 flex w-full max-w-[18rem] flex-col overflow-hidden rounded-lg border text-left',
          onOpenFile ? 'hover:bg-background/80 cursor-pointer' : 'cursor-default'
        )}
        title={onOpenFile ? `Open @${path}` : `@${path}`}
        onClick={() => onOpenFile?.(path)}
        onKeyDown={event => {
          if (!onOpenFile) return
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onOpenFile(path)
          }
        }}
      >
        <div className="relative h-44 w-full overflow-hidden">
          <PdfFirstPagePreview
            title={name}
            base64={pdfBase64}
            url={src}
            zoom={1.25}
            onError={() => setFailed(true)}
          />
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs">
          <FileText className="text-muted-foreground size-3.5 shrink-0" />
          <span className="truncate">{name}</span>
        </div>
      </div>
    )
  }

  if (!src) {
    return (
      <div
        className={cn(
          'bg-background/60 animate-pulse rounded-lg',
          kind === 'video'
            ? 'h-52 w-36'
            : kind === 'audio'
              ? 'h-16 w-full max-w-[18rem]'
              : 'h-40 w-56'
        )}
        aria-hidden
      />
    )
  }

  if (kind === 'audio') {
    return (
      <AudioPlayPreview
        src={src}
        title={name}
        mode="card"
        onError={() => setFailed(true)}
        onOpen={onOpenFile ? () => onOpenFile(path) : undefined}
      />
    )
  }

  if (kind === 'video') {
    return (
      <div className="flex max-w-[14rem] flex-col gap-1">
        <VideoPlayPreview
          src={src}
          mode="card"
          onError={() => setFailed(true)}
        />
        {onOpenFile ? (
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground truncate px-0.5 text-left text-xs"
            title={`Open @${path}`}
            onClick={() => onOpenFile(path)}
          >
            {name}
          </button>
        ) : (
          <div className="text-muted-foreground truncate px-0.5 text-xs">
            {name}
          </div>
        )}
      </div>
    )
  }

  if (kind === 'image') {
    const img = (
      <img
        src={src}
        alt={name}
        className={cn(
          'max-h-64 max-w-full rounded-lg object-contain transition-opacity',
          loaded ? 'opacity-100' : 'opacity-0'
        )}
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(true)}
      />
    )
    if (onOpenFile) {
      return (
        <button
          type="button"
          className="bg-background/40 block max-w-full cursor-pointer overflow-hidden rounded-lg text-left"
          title={`Open @${path}`}
          onClick={() => onOpenFile(path)}
        >
          {img}
        </button>
      )
    }
    return <div className="max-w-full overflow-hidden rounded-lg">{img}</div>
  }

  return null
}
