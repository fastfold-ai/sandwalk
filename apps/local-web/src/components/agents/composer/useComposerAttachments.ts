import { useCallback, useEffect, useRef, useState } from 'react'

import { fileChipToken } from '@/components/agents/composer-parts'
import type { ComposerAttachmentItem } from '@/components/agents/composer/ComposerAttachments'

export type UploadedComposerFile = {
  path: string
  name: string
  mimeType?: string
}

export function useComposerAttachments(
  onUploadFiles: (files: File[]) => Promise<UploadedComposerFile[]>,
  /** Clear attachments when the composer session changes. */
  resetKey?: string | null
) {
  const [attachments, setAttachments] = useState<ComposerAttachmentItem[]>([])
  const attachmentsRef = useRef(attachments)
  attachmentsRef.current = attachments

  const revokePreview = useCallback((item: ComposerAttachmentItem) => {
    if (item.previewUrl?.startsWith('blob:')) {
      URL.revokeObjectURL(item.previewUrl)
    }
  }, [])

  const clearAttachments = useCallback(() => {
    for (const item of attachmentsRef.current) revokePreview(item)
    setAttachments([])
  }, [revokePreview])

  useEffect(() => {
    clearAttachments()
  }, [resetKey, clearAttachments])

  const removeAttachment = useCallback(
    (id: string) => {
      setAttachments(current => {
        const target = current.find(item => item.id === id)
        if (target) revokePreview(target)
        return current.filter(item => item.id !== id)
      })
    },
    [revokePreview]
  )

  const addFiles = useCallback(
    async (fileList: FileList | File[]) => {
      const files = Array.from(fileList)
      if (files.length === 0) return

      const pending: ComposerAttachmentItem[] = files.map(file => ({
        id: crypto.randomUUID(),
        name: file.name,
        contentType: file.type || 'application/octet-stream',
        previewUrl:
          file.type.startsWith('image/') ||
          file.type.startsWith('video/') ||
          file.type.startsWith('audio/')
            ? URL.createObjectURL(file)
            : undefined,
        status: 'uploading'
      }))

      setAttachments(current => [...current, ...pending])

      try {
        const uploaded = await onUploadFiles(files)
        setAttachments(current =>
          current.map(item => {
            const index = pending.findIndex(p => p.id === item.id)
            if (index === -1) return item
            const result = uploaded[index]
            if (!result) {
              return {
                ...item,
                status: 'error',
                error: 'Upload failed'
              }
            }
            return {
              ...item,
              path: result.path,
              name: result.name || item.name,
              contentType: result.mimeType || item.contentType,
              status: 'ready'
            }
          })
        )
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Upload failed'
        setAttachments(current =>
          current.map(item =>
            pending.some(p => p.id === item.id)
              ? { ...item, status: 'error', error: message }
              : item
          )
        )
      }
    },
    [onUploadFiles]
  )

  const attachmentSendPrefix = useCallback(() => {
    return attachmentsRef.current
      .filter(item => item.status === 'ready' && item.path)
      .map(item => fileChipToken(item.path!))
      .join(' ')
  }, [])

  const hasReadyAttachments = attachments.some(
    item => item.status === 'ready' && item.path
  )
  const isUploading = attachments.some(item => item.status === 'uploading')

  return {
    attachments,
    addFiles,
    removeAttachment,
    clearAttachments,
    attachmentSendPrefix,
    hasReadyAttachments,
    isUploading
  }
}
