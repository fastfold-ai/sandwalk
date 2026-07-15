import type {
  WorkspaceFile,
  WorkspaceFileContent
} from '@sandwalk/agent-ui-core'

export type ViewMode = 'list' | 'grid'

/** Idle delay after the last keystroke before autosaving Monaco drafts. */
export const AUTOSAVE_DELAY_MS = 1500

export type ArtifactGroup = {
  id: string
  title: string
  files: WorkspaceFile[]
}

type PersistedFileTabs = {
  paths: string[]
  activePath: string | null
  filesTabActive: boolean
  viewMode?: ViewMode
}

const OPEN_FILE_TABS_STORAGE_KEY = 'fastfold.open-file-tabs'

export function readOpenFileTabs(sessionId: string): PersistedFileTabs {
  try {
    const raw = localStorage.getItem(OPEN_FILE_TABS_STORAGE_KEY)
    if (!raw) return { paths: [], activePath: null, filesTabActive: true }
    const parsed = JSON.parse(raw) as Record<string, PersistedFileTabs>
    const entry = parsed?.[sessionId]
    if (!entry || !Array.isArray(entry.paths)) {
      return { paths: [], activePath: null, filesTabActive: true }
    }
    return {
      paths: entry.paths.filter(
        (path): path is string => typeof path === 'string' && path.length > 0
      ),
      activePath:
        typeof entry.activePath === 'string' ? entry.activePath : null,
      filesTabActive: entry.filesTabActive !== false,
      viewMode:
        entry.viewMode === 'grid' || entry.viewMode === 'list'
          ? entry.viewMode
          : undefined
    }
  } catch {
    return { paths: [], activePath: null, filesTabActive: true }
  }
}

export function writeOpenFileTabs(sessionId: string, state: PersistedFileTabs) {
  try {
    const raw = localStorage.getItem(OPEN_FILE_TABS_STORAGE_KEY)
    const parsed = raw
      ? (JSON.parse(raw) as Record<string, PersistedFileTabs>)
      : {}
    parsed[sessionId] = state
    localStorage.setItem(OPEN_FILE_TABS_STORAGE_KEY, JSON.stringify(parsed))
  } catch {
    // ignore storage failures
  }
}

export function isStructure(path: string) {
  return /\.(pdb|cif|mmcif|sdf)$/i.test(path)
}

export function isSvg(path: string) {
  return /\.svg$/i.test(path)
}

export function isSpreadsheet(path: string) {
  return /\.(csv|tsv)$/i.test(path)
}

export function isTextLike(path: string) {
  return /\.(json|md|txt|ya?ml|py|ts|tsx|js|jsx|css|html?|xml|cif|mmcif|pdb|sdf)$/i.test(
    path
  )
}

export function normalizeFileContent(
  content: WorkspaceFileContent
): WorkspaceFileContent {
  if (
    content.encoding === 'base64' &&
    (isStructure(content.path) || isTextLike(content.path))
  ) {
    try {
      return {
        ...content,
        content: atob(content.content),
        encoding: 'text'
      }
    } catch {
      return content
    }
  }
  return content
}

export function groupArtifacts(files: WorkspaceFile[]): ArtifactGroup[] {
  const onlyFiles = files.filter(file => file.type === 'file')
  const buckets = new Map<string, WorkspaceFile[]>()

  for (const file of onlyFiles) {
    const parts = file.path.split('/').filter(Boolean)
    let key = 'Artifacts'
    if (parts[0]?.toLowerCase() === 'uploads') key = 'Your uploads'
    else if (parts[0]?.toLowerCase() === 'outputs') key = 'Generated outputs'
    else if (parts.length > 1) key = parts[0]
    const bucket = buckets.get(key) || []
    bucket.push(file)
    buckets.set(key, bucket)
  }

  const preferred = ['Your uploads', 'Generated outputs', 'Artifacts']
  const keys = [
    ...preferred.filter(key => buckets.has(key)),
    ...[...buckets.keys()].filter(key => !preferred.includes(key)).sort()
  ]
  return keys.map(title => ({
    id: title,
    title,
    files: (buckets.get(title) || []).sort((a, b) =>
      a.name.localeCompare(b.name)
    )
  }))
}

export function fileTextContent(
  active: WorkspaceFileContent,
  draft: string
): string {
  if (active.encoding === 'text') return draft || active.content
  if (isStructure(active.path) || isTextLike(active.path)) {
    try {
      return atob(active.content)
    } catch {
      return active.content
    }
  }
  return draft || active.content
}

export function languageFor(path: string) {
  const extension = path.split('.').at(-1)?.toLowerCase()
  return (
    {
      py: 'python',
      ts: 'typescript',
      tsx: 'typescript',
      js: 'javascript',
      jsx: 'javascript',
      json: 'json',
      md: 'markdown',
      yaml: 'yaml',
      yml: 'yaml',
      css: 'css',
      html: 'html',
      htm: 'html',
      xml: 'xml',
      svg: 'xml',
      csv: 'plaintext',
      pdb: 'plaintext',
      cif: 'plaintext',
      mmcif: 'plaintext',
      sdf: 'plaintext'
    }[extension || ''] || 'plaintext'
  )
}
