import { describe, expect, it } from 'vitest'

import {
  splitTextWithWorkspacePaths,
  workspaceRelativeFromPath
} from './workspace-file-paths'

const abs =
  '/Users/juliocesar/.sandwalk/workspaces/bffbda43-b9f7-48b7-bb45-8fe29dd4f2dd/artifacts/sample_plot.png'

describe('workspaceRelativeFromPath', () => {
  it('strips absolute sandwalk workspace roots', () => {
    expect(workspaceRelativeFromPath(abs)).toBe('artifacts/sample_plot.png')
  })

  it('handles tilde form and trailing punctuation', () => {
    expect(
      workspaceRelativeFromPath(
        '~/.sandwalk/workspaces/abc-123/plans/demo.md.'
      )
    ).toBe('plans/demo.md')
  })

  it('uses an explicit workspace root', () => {
    const root =
      '/Users/juliocesar/.sandwalk/workspaces/bffbda43-b9f7-48b7-bb45-8fe29dd4f2dd'
    expect(workspaceRelativeFromPath(`${root}/notes.txt`, root)).toBe(
      'notes.txt'
    )
  })

  it('returns null for non-workspace paths', () => {
    expect(workspaceRelativeFromPath('/tmp/foo.png')).toBeNull()
    expect(workspaceRelativeFromPath('artifacts/sample_plot.png')).toBeNull()
  })
})

describe('splitTextWithWorkspacePaths', () => {
  it('linkifies absolute workspace paths in prose', () => {
    const parts = splitTextWithWorkspacePaths(
      `saved to ${abs} for review.`
    )
    expect(parts).toEqual([
      { type: 'text', text: 'saved to ' },
      {
        type: 'file',
        absolute: abs,
        relative: 'artifacts/sample_plot.png'
      },
      { type: 'text', text: ' for review.' }
    ])
  })
})
