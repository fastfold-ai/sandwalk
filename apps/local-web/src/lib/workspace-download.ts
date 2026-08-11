import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFile, WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import { toast } from 'sonner'

import { isTauri, saveBytesFile, saveTextFile } from '@/lib/desktop'

function bytesFromContent(file: WorkspaceFileContent): Uint8Array {
  if (file.encoding === 'base64') {
    const binary = atob(file.content)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    return bytes
  }
  return new TextEncoder().encode(file.content)
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
  }
  return btoa(binary)
}

function triggerBrowserDownload(filename: string, bytes: Uint8Array, mime: string) {
  const copy = new Uint8Array(bytes.byteLength)
  copy.set(bytes)
  const href = URL.createObjectURL(new Blob([copy], { type: mime }))
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}

export function toastDownloadPath(path: string, label = 'Saved') {
  toast.success(label, {
    description: path,
    duration: 6000
  })
}

/** CRC-32 (ISO-HDLC) for ZIP local/central headers. */
function crc32(data: Uint8Array): number {
  let crc = 0xffffffff
  for (let i = 0; i < data.length; i++) {
    crc ^= data[i]
    for (let bit = 0; bit < 8; bit++) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1))
    }
  }
  return (crc ^ 0xffffffff) >>> 0
}

function u16(value: number): Uint8Array {
  const out = new Uint8Array(2)
  out[0] = value & 0xff
  out[1] = (value >>> 8) & 0xff
  return out
}

function u32(value: number): Uint8Array {
  const out = new Uint8Array(4)
  out[0] = value & 0xff
  out[1] = (value >>> 8) & 0xff
  out[2] = (value >>> 16) & 0xff
  out[3] = (value >>> 24) & 0xff
  return out
}

function concatBytes(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0)
  const out = new Uint8Array(total)
  let offset = 0
  for (const part of parts) {
    out.set(part, offset)
    offset += part.length
  }
  return out
}

/** Uncompressed ZIP (STORE) — enough for artifact bundles without extra deps. */
export function buildZipStore(
  entries: Array<{ name: string; data: Uint8Array }>
): Uint8Array {
  const locals: Uint8Array[] = []
  const centrals: Uint8Array[] = []
  let offset = 0

  for (const entry of entries) {
    const name = entry.name.replace(/^\/+/, '').replace(/\\/g, '/')
    const nameBytes = new TextEncoder().encode(name)
    const data = entry.data
    const crc = crc32(data)
    const local = concatBytes([
      u32(0x04034b50),
      u16(20),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(crc),
      u32(data.length),
      u32(data.length),
      u16(nameBytes.length),
      u16(0),
      nameBytes,
      data
    ])
    const central = concatBytes([
      u32(0x02014b50),
      u16(20),
      u16(20),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(crc),
      u32(data.length),
      u32(data.length),
      u16(nameBytes.length),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(0),
      u32(offset),
      nameBytes
    ])
    locals.push(local)
    centrals.push(central)
    offset += local.length
  }

  const centralDir = concatBytes(centrals)
  const end = concatBytes([
    u32(0x06054b50),
    u16(0),
    u16(0),
    u16(entries.length),
    u16(entries.length),
    u32(centralDir.length),
    u32(offset),
    u16(0)
  ])
  return concatBytes([...locals, centralDir, end])
}

async function persistBytes(filename: string, bytes: Uint8Array): Promise<string | null> {
  if (isTauri()) {
    return saveBytesFile(filename, bytesToBase64(bytes))
  }
  triggerBrowserDownload(filename, bytes, 'application/octet-stream')
  return null
}

export async function downloadWorkspaceFile(
  client: LocalAgentClient,
  sessionId: string,
  path: string
): Promise<void> {
  const name = path.split('/').filter(Boolean).at(-1) || 'download'
  const toastId = toast.loading(`Downloading ${name}…`)
  try {
    const file = await client.readFile(sessionId, path)
    const bytes = bytesFromContent(file)
    const saved = await persistBytes(name, bytes)
    toast.dismiss(toastId)
    if (saved) toastDownloadPath(saved, `Downloaded ${name}`)
    else toast.success(`Downloaded ${name}`)
  } catch (cause) {
    toast.dismiss(toastId)
    toast.error(
      cause instanceof Error ? cause.message : `Failed to download ${name}`
    )
    throw cause
  }
}

export async function downloadWorkspaceZip(
  client: LocalAgentClient,
  sessionId: string,
  files: WorkspaceFile[],
  zipName = 'artifacts.zip'
): Promise<void> {
  const targets = files.filter(file => file.type === 'file')
  if (targets.length === 0) {
    toast.message('No files to download')
    return
  }
  const toastId = toast.loading(
    `Preparing zip (${targets.length} file${targets.length === 1 ? '' : 's'})…`
  )
  try {
    const entries: Array<{ name: string; data: Uint8Array }> = []
    for (const file of targets) {
      const content = await client.readFile(sessionId, file.path)
      entries.push({
        name: file.path.replace(/^\/+/, ''),
        data: bytesFromContent(content)
      })
    }
    const zipBytes = buildZipStore(entries)
    const saved = await persistBytes(zipName, zipBytes)
    toast.dismiss(toastId)
    if (saved) {
      toastDownloadPath(
        saved,
        `Downloaded ${targets.length} file${targets.length === 1 ? '' : 's'}`
      )
    } else {
      toast.success(`Downloaded ${zipName}`)
    }
  } catch (cause) {
    toast.dismiss(toastId)
    toast.error(
      cause instanceof Error ? cause.message : 'Failed to download artifacts'
    )
    throw cause
  }
}

export async function downloadTextWithLocation(
  filename: string,
  content: string
): Promise<string | null> {
  if (isTauri()) {
    const path = await saveTextFile(filename, content)
    toastDownloadPath(path, 'Exported')
    return path
  }
  triggerBrowserDownload(
    filename,
    new TextEncoder().encode(content),
    'text/markdown;charset=utf-8'
  )
  toast.success(`Downloaded ${filename}`)
  return null
}
