import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useComposerAttachments } from './useComposerAttachments'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useComposerAttachments', () => {
  it('tracks upload progress and builds send prefix tokens', async () => {
    const onUpload = vi.fn(async (files: File[]) =>
      files.map(file => ({
        path: `uploads/${file.name}`,
        name: file.name,
        mimeType: file.type
      }))
    )

    const { result } = renderHook(() =>
      useComposerAttachments(onUpload, 'session-1')
    )

    const file = new File(['hello'], 'note.txt', { type: 'text/plain' })
    await act(async () => {
      await result.current.addFiles([file])
    })

    await waitFor(() => {
      expect(result.current.attachments).toHaveLength(1)
      expect(result.current.attachments[0]?.status).toBe('ready')
      expect(result.current.attachments[0]?.path).toBe('uploads/note.txt')
    })

    expect(result.current.attachmentSendPrefix()).toBe('⟦@:uploads/note.txt⟧')
    expect(result.current.hasReadyAttachments).toBe(true)
  })

  it('marks failed uploads and clears on reset key change', async () => {
    const onUpload = vi.fn(async () => {
      throw new Error('network')
    })

    const { result, rerender } = renderHook(
      ({ key }) => useComposerAttachments(onUpload, key),
      { initialProps: { key: 'a' } }
    )

    const file = new File(['x'], 'x.png', { type: 'image/png' })
    await act(async () => {
      await result.current.addFiles([file])
    })

    await waitFor(() => {
      expect(result.current.attachments[0]?.status).toBe('error')
    })

    rerender({ key: 'b' })
    await waitFor(() => {
      expect(result.current.attachments).toHaveLength(0)
    })
  })
})
