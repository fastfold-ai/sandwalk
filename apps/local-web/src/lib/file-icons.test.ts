import { describe, expect, it } from 'vitest'

import { getFileIcon } from './file-icons'

describe('getFileIcon', () => {
  it('maps common extensions', () => {
    expect(getFileIcon('notes.md')).toBe('vscode-icons:file-type-markdown')
    expect(getFileIcon('app.tsx')).toBe('vscode-icons:file-type-reactts')
    expect(getFileIcon('script.py')).toBe('vscode-icons:file-type-python')
    expect(getFileIcon('data.json')).toBe('vscode-icons:file-type-json')
    expect(getFileIcon('struct.pdb')).toBe('vscode-icons:file-type-moleculer')
  })

  it('handles special filenames', () => {
    expect(getFileIcon('Dockerfile')).toBe('vscode-icons:file-type-docker')
    expect(getFileIcon('README.md')).toBe('vscode-icons:file-type-readme')
    expect(getFileIcon('readme')).toBe('vscode-icons:file-type-readme')
    expect(getFileIcon('.env.local')).toBe('vscode-icons:file-type-dotenv')
  })

  it('falls back for unknown types', () => {
    expect(getFileIcon('archive.xyz')).toBe('vscode-icons:default-file')
    expect(getFileIcon('noext')).toBe('vscode-icons:default-file')
  })
})
