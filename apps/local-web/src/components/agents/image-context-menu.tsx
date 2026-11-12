import { Copy, Download, ExternalLink, MessageSquarePlus } from 'lucide-react'
import { type ReactNode, useState } from 'react'

import {
  TabContextItem,
  TabContextMenuShell
} from '@/components/agents/tab-context-menu'
import { isTauri, pickSavePath, saveBytesToPath } from '@/lib/desktop'

export const COMPOSER_ADD_FILE_EVENT = 'sandwalk:composer-add-file'

function filenameFrom(src: string, filename?: string) {
  if (filename?.trim()) return filename.trim()
  try {
    const url = new URL(src, window.location.href)
    const leaf = url.pathname.split('/').pop()
    if (leaf) return decodeURIComponent(leaf)
  } catch {
    // Data and blob URLs have no path.
  }
  return 'image.png'
}

async function imageBlob(src: string): Promise<Blob> {
  const response = await fetch(src)
  if (!response.ok) throw new Error('image fetch failed')
  return response.blob()
}

function fileExtension(name: string) {
  const leaf = name.split('.').pop()?.toLowerCase()
  if (leaf && ['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(leaf)) {
    return leaf === 'jpeg' ? 'jpg' : leaf
  }
  return 'png'
}

function bytesToBase64(bytes: Uint8Array) {
  let binary = ''
  const chunk = 0x8000
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunk))
  }
  return btoa(binary)
}

type SavePickerWindow = Window & {
  showSaveFilePicker?: (options: {
    suggestedName?: string
    types?: { description?: string; accept: Record<string, string[]> }[]
  }) => Promise<{
    createWritable: () => Promise<{
      write: (data: Blob) => Promise<void>
      close: () => Promise<void>
    }>
  }>
}

/** Save panel with a folder list. Desktop uses the native dialog. */
async function saveImageCopy(src: string, name: string) {
  const extension = fileExtension(name)
  if (isTauri()) {
    const chosen = await pickSavePath({
      defaultPath: name,
      title: 'Save image',
      extensions: [extension]
    })
    if (!chosen) return
    const blob = await imageBlob(src)
    const bytes = new Uint8Array(await blob.arrayBuffer())
    await saveBytesToPath(chosen, bytesToBase64(bytes))
    return
  }

  const picker = (window as SavePickerWindow).showSaveFilePicker
  if (picker) {
    const mime = extension === 'jpg' ? 'image/jpeg' : `image/${extension}`
    let handle: Awaited<ReturnType<typeof picker>>
    try {
      handle = await picker({
        suggestedName: name,
        types: [
          {
            description: 'Image',
            accept: { [mime]: [`.${extension}`] }
          }
        ]
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      throw error
    }
    const blob = await imageBlob(src)
    const writable = await handle.createWritable()
    await writable.write(blob)
    await writable.close()
    return
  }

  const link = document.createElement('a')
  link.href = src
  link.download = name
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

export function ImageContextTarget({
  src,
  filename,
  workspacePath,
  className,
  children
}: {
  src: string
  filename?: string
  /** Workspace-relative path. Enables "Add to chat". */
  workspacePath?: string | null
  className?: string
  children: ReactNode
}) {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null)
  const name = filenameFrom(src, filename)
  const close = () => setMenu(null)

  const copyImage = () => {
    void imageBlob(src)
      .then(blob =>
        navigator.clipboard.write([
          new ClipboardItem({ [blob.type || 'image/png']: blob })
        ])
      )
      .catch(() => undefined)
  }
  const downloadImage = () => {
    void saveImageCopy(src, name)
  }

  return (
    <div
      className={`group/image relative overflow-hidden rounded-[2rem] ${className ?? ''}`}
      onContextMenu={event => {
        event.preventDefault()
        event.stopPropagation()
        setMenu({ x: event.clientX, y: event.clientY })
      }}
    >
      {children}
      <div className="pointer-events-none absolute top-3 right-3 z-10 flex gap-1.5 opacity-0 transition-opacity group-hover/image:pointer-events-auto group-hover/image:opacity-100 group-focus-within/image:pointer-events-auto group-focus-within/image:opacity-100">
        <button
          type="button"
          title="Download a copy"
          aria-label="Download a copy"
          className="flex size-9 items-center justify-center rounded-full bg-black/70 text-white shadow-sm backdrop-blur-md hover:bg-black/80"
          onClick={event => {
            event.preventDefault()
            event.stopPropagation()
            downloadImage()
          }}
        >
          <Download className="size-4" />
        </button>
        <button
          type="button"
          title="Copy image"
          aria-label="Copy image"
          className="flex size-9 items-center justify-center rounded-full bg-black/70 text-white shadow-sm backdrop-blur-md hover:bg-black/80"
          onClick={event => {
            event.preventDefault()
            event.stopPropagation()
            copyImage()
          }}
        >
          <Copy className="size-4" />
        </button>
      </div>
      {menu ? (
        <TabContextMenuShell x={menu.x} y={menu.y} onClose={close}>
          <TabContextItem
            icon={<ExternalLink />}
            label="Open image in new tab"
            onClick={() => {
              close()
              window.open(src, '_blank', 'noopener,noreferrer')
            }}
          />
          {workspacePath ? (
            <TabContextItem
              icon={<MessageSquarePlus />}
              label="Add to chat"
              onClick={() => {
                close()
                window.dispatchEvent(
                  new CustomEvent(COMPOSER_ADD_FILE_EVENT, {
                    detail: { path: workspacePath }
                  })
                )
              }}
            />
          ) : null}
          <TabContextItem
            icon={<Copy />}
            label="Copy image"
            onClick={() => {
              close()
              copyImage()
            }}
          />
          <TabContextItem
            icon={<Download />}
            label="Download a copy"
            onClick={() => {
              close()
              downloadImage()
            }}
          />
        </TabContextMenuShell>
      ) : null}
    </div>
  )
}
