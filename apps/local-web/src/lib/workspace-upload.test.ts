import { describe, expect, it } from 'vitest'

import { formatWorkspaceUploadError } from './workspace-upload'

describe('workspace-upload', () => {
  it('parses API detail from upload errors', () => {
    expect(
      formatWorkspaceUploadError(
        new Error('FastFold Agent API 500: {"detail":"disk full"}')
      )
    ).toBe('disk full')
  })

  it('falls back to the raw message', () => {
    expect(formatWorkspaceUploadError(new Error('network'))).toBe('network')
  })
})
