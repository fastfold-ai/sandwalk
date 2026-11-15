import { describe, expect, it } from 'vitest'

import {
  messageFilePreviewKind,
  responseImageSources,
  workspaceImagePathsInText
} from '@/components/agents/message-file-preview'

describe('workspaceImagePathsInText', () => {
  it('keeps workspace image paths and ignores other files', () => {
    const text = [
      'Saved to /Users/andxeg/.sandwalk/workspaces/abc/artifacts/capybara.jpg',
      'and notes.txt'
    ].join(' ')
    expect(workspaceImagePathsInText(text)).toEqual(['artifacts/capybara.jpg'])
  })
})

describe('responseImageSources', () => {
  it('keeps one workspace file and drops the matching data url', () => {
    const text = 'Saved to /Users/a/.sandwalk/workspaces/abc/artifacts/images/star.png'
    const sources = responseImageSources(
      text,
      [],
      undefined,
      ['data:image/png;base64,aaaa']
    )
    expect(sources.paths).toEqual(['artifacts/images/star.png'])
    expect(sources.urls).toEqual([])
  })

  it('drops the remote image link when the file was saved', () => {
    const sources = responseImageSources(
      'Saved to /Users/a/.sandwalk/workspaces/abc/artifacts/images/red_circle.webp',
      ['Image URL: https://example.com/image.webp'],
      undefined,
      ['https://example.com/image.webp', 'data:image/webp;base64,aaaa']
    )
    expect(sources.paths).toEqual(['artifacts/images/red_circle.webp'])
    expect(sources.urls).toEqual([])
  })

  it('keeps one remote url when nothing was saved', () => {
    const sources = responseImageSources(
      '',
      ['Image URL: https://example.com/image.webp'],
      undefined,
      ['data:image/webp;base64,aaaa', 'https://example.com/image.webp']
    )
    expect(sources.paths).toEqual([])
    expect(sources.urls).toEqual(['https://example.com/image.webp'])
  })
})

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


