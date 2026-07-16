import { describe, expect, it } from 'vitest'

import { messageFilePreviewKind } from '@/components/agents/message-file-preview'

describe('messageFilePreviewKind', () => {
  it('detects common image extensions', () => {
    expect(messageFilePreviewKind('mmm.png')).toBe('image')
    expect(messageFilePreviewKind('shots/capybara.JPEG')).toBe('image')
    expect(messageFilePreviewKind('a/b/c.webp')).toBe('image')
  })

  it('detects PDFs only among document types', () => {
    expect(messageFilePreviewKind('report.pdf')).toBe('pdf')
    expect(messageFilePreviewKind('deck.pptx')).toBeNull()
    expect(messageFilePreviewKind('notes.txt')).toBeNull()
  })

  it('detects common video extensions', () => {
    expect(messageFilePreviewKind('clip.mp4')).toBe('video')
    expect(messageFilePreviewKind('a/b/demo.WEBM')).toBe('video')
    expect(messageFilePreviewKind('take.mov')).toBe('video')
  })

  it('detects common audio extensions', () => {
    expect(messageFilePreviewKind('track.mp3')).toBe('audio')
    expect(messageFilePreviewKind('uploads/sample.WAV')).toBe('audio')
    expect(messageFilePreviewKind('a/b/clip.flac')).toBe('audio')
  })

  it('detects structure files for inline Mol* preview', () => {
    expect(messageFilePreviewKind('test.cif')).toBe('structure')
    expect(messageFilePreviewKind('models/1abc.PDB')).toBe('structure')
    expect(messageFilePreviewKind('a/b/complex.mmcif')).toBe('structure')
    expect(messageFilePreviewKind('ligand.sdf')).toBe('structure')
  })
})


