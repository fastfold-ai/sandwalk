import { describe, expect, it } from 'vitest'

import {
  dragAcceptsComposerDrop,
  dragHasFiles
} from './useComposerFileDrop'
import {
  dragHasWorkspacePath,
  getWorkspacePathDragData,
  setWorkspacePathDragData,
  WORKSPACE_PATH_MIME
} from './workspace-path-drag'

describe('dragHasFiles', () => {
  it('detects Files in dataTransfer types', () => {
    const event = {
      dataTransfer: { types: ['Files', 'text/plain'] }
    } as unknown as DragEvent
    expect(dragHasFiles(event as never)).toBe(true)
  })

  it('returns false without Files', () => {
    const event = {
      dataTransfer: { types: ['text/plain'] }
    } as unknown as DragEvent
    expect(dragHasFiles(event as never)).toBe(false)
  })
})

describe('workspace path drag', () => {
  it('sets and reads workspace path payload', () => {
    const store = new Map<string, string>()
    const dataTransfer = {
      types: [] as string[],
      effectAllowed: 'none',
      setData(type: string, value: string) {
        store.set(type, value)
        if (!this.types.includes(type)) this.types.push(type)
      },
      getData(type: string) {
        return store.get(type) || ''
      }
    }
    setWorkspacePathDragData(dataTransfer as unknown as DataTransfer, {
      path: 'skills/fold',
      type: 'directory'
    })
    expect(dataTransfer.types).toContain(WORKSPACE_PATH_MIME)
    expect(getWorkspacePathDragData(dataTransfer as unknown as DataTransfer)).toEqual({
      path: 'skills/fold',
      type: 'directory'
    })
    expect(
      dragHasWorkspacePath({
        dataTransfer: dataTransfer as unknown as DataTransfer
      })
    ).toBe(true)
    expect(
      dragAcceptsComposerDrop({
        dataTransfer: dataTransfer
      } as never)
    ).toBe(true)
  })
})
