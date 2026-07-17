import { describe, expect, it } from 'vitest'

import { groupArtifacts } from './workspace-utils'

describe('groupArtifacts', () => {
  it('shows empty user folders as their own group', () => {
    const groups = groupArtifacts([
      {
        path: 'test',
        name: 'test',
        type: 'directory',
        size: null,
        mtime: null
      }
    ])
    expect(groups).toEqual([
      { id: 'test', title: 'test', files: [] }
    ])
  })

  it('hides empty scaffold folders', () => {
    const groups = groupArtifacts([
      {
        path: 'uploads',
        name: 'uploads',
        type: 'directory',
        size: null,
        mtime: null
      },
      {
        path: 'outputs',
        name: 'outputs',
        type: 'directory',
        size: null,
        mtime: null
      }
    ])
    expect(groups).toEqual([])
  })

  it('lists nested folders and files under the top-level group', () => {
    const groups = groupArtifacts([
      {
        path: 'test',
        name: 'test',
        type: 'directory',
        size: null,
        mtime: null
      },
      {
        path: 'test/sub',
        name: 'sub',
        type: 'directory',
        size: null,
        mtime: null
      },
      {
        path: 'test/notes.md',
        name: 'notes.md',
        type: 'file',
        size: 1,
        mtime: null
      }
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].title).toBe('test')
    expect(groups[0].files.map(item => item.path)).toEqual([
      'test/sub',
      'test/notes.md'
    ])
  })
})
