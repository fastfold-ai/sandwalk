import { type DragEvent, useCallback, useRef, useState } from 'react'

import {
  dragHasWorkspacePath,
  getWorkspacePathDragData,
  type WorkspacePathDragPayload
} from '@/components/agents/composer/workspace-path-drag'

/** True when the drag payload includes files (OS / Finder drops). */
export function dragHasFiles(event: DragEvent | DragEvent<Element>) {
  const types = event.dataTransfer?.types
  if (!types) return false
  return Array.from(types).includes('Files')
}

export function dragAcceptsComposerDrop(
  event: DragEvent | DragEvent<Element>
): boolean {
  return dragHasWorkspacePath(event) || dragHasFiles(event)
}

export type ComposerDropKind = 'upload' | 'reference' | null

/**
 * Composer drag-and-drop: OS files upload, or Artifacts panel path references.
 * Uses a depth counter so entering child nodes does not flicker the overlay.
 */
export function useComposerFileDrop({
  onFiles,
  onWorkspacePath
}: {
  onFiles: (files: FileList | File[]) => void
  onWorkspacePath?: (payload: WorkspacePathDragPayload) => void
}) {
  const [dragging, setDragging] = useState<ComposerDropKind>(null)
  const depthRef = useRef(0)

  const kindForEvent = useCallback(
    (event: DragEvent | DragEvent<Element>): ComposerDropKind => {
      if (dragHasWorkspacePath(event)) return 'reference'
      if (dragHasFiles(event)) return 'upload'
      return null
    },
    []
  )

  const reset = useCallback(() => {
    depthRef.current = 0
    setDragging(null)
  }, [])

  const onDragEnter = useCallback(
    (event: DragEvent<HTMLElement>) => {
      const kind = kindForEvent(event)
      if (!kind) return
      event.preventDefault()
      event.stopPropagation()
      depthRef.current += 1
      setDragging(kind)
    },
    [kindForEvent]
  )

  const onDragOver = useCallback(
    (event: DragEvent<HTMLElement>) => {
      const kind = kindForEvent(event)
      if (!kind) return
      event.preventDefault()
      event.stopPropagation()
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'copy'
      }
      setDragging(kind)
    },
    [kindForEvent]
  )

  const onDragLeave = useCallback(
    (event: DragEvent<HTMLElement>) => {
      if (!kindForEvent(event)) return
      event.preventDefault()
      event.stopPropagation()
      depthRef.current = Math.max(0, depthRef.current - 1)
      if (depthRef.current === 0) setDragging(null)
    },
    [kindForEvent]
  )

  const onDrop = useCallback(
    (event: DragEvent<HTMLElement>) => {
      event.preventDefault()
      event.stopPropagation()
      reset()
      const workspacePath = getWorkspacePathDragData(event.dataTransfer)
      if (workspacePath) {
        onWorkspacePath?.(workspacePath)
        return
      }
      const files = event.dataTransfer?.files
      if (files?.length) onFiles(files)
    },
    [onFiles, onWorkspacePath, reset]
  )

  return {
    dragging,
    dropHandlers: {
      onDragEnter,
      onDragOver,
      onDragLeave,
      onDrop
    }
  }
}
