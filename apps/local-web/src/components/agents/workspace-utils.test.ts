import { describe, expect, it } from 'vitest'

import {
  childrenOf,
  compareArtifacts,
  groupArtifacts,
  groupRootPath,
  parentDir
} from './workspace-utils'

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

  it('sorts by mtime newest first within type', () => {
    const groups = groupArtifacts([
      {
        path: 'proj/old.py',
        name: 'old.py',
        type: 'file',
        size: 1,
        mtime: '2026-01-01T00:00:00.000Z'
      },
      {
        path: 'proj/new.py',
        name: 'new.py',
        type: 'file',
        size: 1,
        mtime: '2026-06-01T00:00:00.000Z'
      },
      {
        path: 'proj/dir',
        name: 'dir',
        type: 'directory',
        size: null,
        mtime: '2026-03-01T00:00:00.000Z'
      }
    ])
    expect(groups[0].files.map(item => item.path)).toEqual([
      'proj/dir',
      'proj/new.py',
      'proj/old.py'
    ])
  })
})

describe('folder browsing helpers', () => {
  it('parentDir strips the last segment', () => {
    expect(parentDir('a/b/c')).toBe('a/b')
    expect(parentDir('a')).toBe('')
  })

  it('groupRootPath maps labels to filesystem roots', () => {
    expect(groupRootPath('Your uploads')).toBe('uploads')
    expect(groupRootPath('Generated outputs')).toBe('outputs')
    expect(groupRootPath('Project folder')).toBe('project')
    expect(groupRootPath('Artifacts')).toBe('')
    expect(groupRootPath('artifacts')).toBe('artifacts')
  })

  it('labels the project/ mount as Project folder', () => {
    const groups = groupArtifacts([
      {
        path: 'project',
        name: 'project',
        type: 'directory',
        size: null,
        mtime: null
      },
      {
        path: 'project/notes.md',
        name: 'notes.md',
        type: 'file',
        size: 1,
        mtime: null
      }
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].title).toBe('Project folder')
    expect(groups[0].files.map(item => item.path)).toEqual([
      'project/notes.md'
    ])
  })

  it('childrenOf returns only immediate children sorted by mtime', () => {
    const entries = [
      {
        path: 'artifacts/nested/deep.txt',
        name: 'deep.txt',
        type: 'file' as const,
        size: 1,
        mtime: '2026-06-01T00:00:00.000Z'
      },
      {
        path: 'artifacts/nested',
        name: 'nested',
        type: 'directory' as const,
        size: null,
        mtime: '2026-05-01T00:00:00.000Z'
      },
      {
        path: 'artifacts/root.py',
        name: 'root.py',
        type: 'file' as const,
        size: 1,
        mtime: '2026-04-01T00:00:00.000Z'
      }
    ]
    expect(childrenOf(entries, 'artifacts').map(item => item.path)).toEqual([
      'artifacts/nested',
      'artifacts/root.py'
    ])
    expect(childrenOf(entries, 'artifacts/nested').map(item => item.path)).toEqual([
      'artifacts/nested/deep.txt'
    ])
  })

  it('compareArtifacts prefers directories then newer mtime', () => {
    const older = {
      path: 'a.py',
      name: 'a.py',
      type: 'file' as const,
      size: 1,
      mtime: '2026-01-01T00:00:00.000Z'
    }
    const newer = {
      path: 'b.py',
      name: 'b.py',
      type: 'file' as const,
      size: 1,
      mtime: '2026-06-01T00:00:00.000Z'
    }
    const dir = {
      path: 'd',
      name: 'd',
      type: 'directory' as const,
      size: null,
      mtime: '2026-02-01T00:00:00.000Z'
    }
    expect(compareArtifacts(dir, newer)).toBeLessThan(0)
    expect(compareArtifacts(newer, older)).toBeLessThan(0)
  })
})
