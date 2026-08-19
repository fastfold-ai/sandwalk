import { type DragEvent, useCallback, useEffect, useRef, useState } from 'react'

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
function leaveWindow(event: { clientX: number; clientY: number }) {
  return (
    event.clientX <= 0 ||
    event.clientY <= 0 ||
    event.clientX >= window.innerWidth ||
    event.clientY >= window.innerHeight
  )
}

export function useComposerFileDrop({
  onFiles,
  onWorkspacePath,
  captureWindow = false,
  onDraggingChange
}: {
  onFiles: (files: FileList | File[]) => void
  onWorkspacePath?: (payload: WorkspacePathDragPayload) => void
  /** Steal OS/file drops from the rest of the app (Capy overlay). */
  captureWindow?: boolean
  onDraggingChange?: (kind: ComposerDropKind) => void
}) {
  const [dragging, setDragging] = useState<ComposerDropKind>(null)
  const depthRef = useRef(0)
  const onDraggingChangeRef = useRef(onDraggingChange)
  onDraggingChangeRef.current = onDraggingChange
  const onFilesRef = useRef(onFiles)
  onFilesRef.current = onFiles
  const onWorkspacePathRef = useRef(onWorkspacePath)
  onWorkspacePathRef.current = onWorkspacePath

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
    onDraggingChangeRef.current?.(null)
  }, [])

  const markDragging = useCallback((kind: ComposerDropKind) => {
    setDragging(kind)
    onDraggingChangeRef.current?.(kind)
  }, [])

  const onDragEnter = useCallback(
    (event: DragEvent<HTMLElement>) => {
      const kind = kindForEvent(event)
      if (!kind) return
      event.preventDefault()
      event.stopPropagation()
      depthRef.current += 1
      markDragging(kind)
    },
    [kindForEvent, markDragging]
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
      markDragging(kind)
    },
    [kindForEvent, markDragging]
  )

  const onDragLeave = useCallback(
    (event: DragEvent<HTMLElement>) => {
      if (!kindForEvent(event)) return
      event.preventDefault()
      event.stopPropagation()
      depthRef.current = Math.max(0, depthRef.current - 1)
      if (depthRef.current === 0) {
        setDragging(null)
        onDraggingChangeRef.current?.(null)
      }
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

  useEffect(() => {
    if (!captureWindow) return
    const enter = (event: globalThis.DragEvent) => {
      const kind = kindForEvent(event as unknown as DragEvent)
      if (!kind) return
      event.preventDefault()
      event.stopPropagation()
      markDragging(kind)
    }
    const over = (event: globalThis.DragEvent) => {
      const kind = kindForEvent(event as unknown as DragEvent)
      if (!kind) return
      event.preventDefault()
      event.stopPropagation()
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
      markDragging(kind)
    }
    const leave = (event: globalThis.DragEvent) => {
      if (!kindForEvent(event as unknown as DragEvent)) return
      event.preventDefault()
      event.stopPropagation()
      if (leaveWindow(event)) reset()
    }
    const drop = (event: globalThis.DragEvent) => {
      const kind = kindForEvent(event as unknown as DragEvent)
      const files = event.dataTransfer?.files
      if (!kind && !files?.length) return
      event.preventDefault()
      event.stopPropagation()
      reset()
      const workspacePath = getWorkspacePathDragData(event.dataTransfer)
      if (workspacePath) {
        onWorkspacePathRef.current?.(workspacePath)
        return
      }
      if (files?.length) onFilesRef.current(files)
    }
    const opts = { capture: true }
    window.addEventListener('dragenter', enter, opts)
    window.addEventListener('dragover', over, opts)
    window.addEventListener('dragleave', leave, opts)
    window.addEventListener('drop', drop, opts)
    return () => {
      window.removeEventListener('dragenter', enter, opts)
      window.removeEventListener('dragover', over, opts)
      window.removeEventListener('dragleave', leave, opts)
      window.removeEventListener('drop', drop, opts)
      reset()
    }
  }, [captureWindow, kindForEvent, markDragging, reset])

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
