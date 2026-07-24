import { type DragEvent, useCallback, useRef, useState } from 'react'

/** True when the drag payload includes files (OS / Finder drops). */
export function dragHasFiles(event: DragEvent | DragEvent<Element>) {
  const types = event.dataTransfer?.types
  if (!types) return false
  return Array.from(types).includes('Files')
}

/**
 * Composer file drag-and-drop: highlight while hovering, auto-upload on drop.
 * Uses a depth counter so entering child nodes does not flicker the overlay.
 */
export function useComposerFileDrop(onFiles: (files: FileList | File[]) => void) {
  const [dragging, setDragging] = useState(false)
  const depthRef = useRef(0)

  const reset = useCallback(() => {
    depthRef.current = 0
    setDragging(false)
  }, [])

  const onDragEnter = useCallback((event: DragEvent<HTMLElement>) => {
    if (!dragHasFiles(event)) return
    event.preventDefault()
    event.stopPropagation()
    depthRef.current += 1
    setDragging(true)
  }, [])

  const onDragOver = useCallback((event: DragEvent<HTMLElement>) => {
    if (!dragHasFiles(event)) return
    event.preventDefault()
    event.stopPropagation()
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = 'copy'
    }
    setDragging(true)
  }, [])

  const onDragLeave = useCallback((event: DragEvent<HTMLElement>) => {
    if (!dragHasFiles(event)) return
    event.preventDefault()
    event.stopPropagation()
    depthRef.current = Math.max(0, depthRef.current - 1)
    if (depthRef.current === 0) setDragging(false)
  }, [])

  const onDrop = useCallback(
    (event: DragEvent<HTMLElement>) => {
      event.preventDefault()
      event.stopPropagation()
      reset()
      const files = event.dataTransfer?.files
      if (files?.length) onFiles(files)
    },
    [onFiles, reset]
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
