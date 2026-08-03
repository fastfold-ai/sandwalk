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

export type PersistedFileTabs = {
  paths: string[]
  activePath: string | null
  filesTabActive: boolean
  viewMode?: ViewMode
  /** Top-level artifact group expand/collapse (per session). */
  expandedGroups?: Record<string, boolean>
  /** Nested folder expand/collapse paths (per session). */
  expandedDirs?: Record<string, boolean>
}

const OPEN_FILE_TABS_STORAGE_KEY = 'fastfold.open-file-tabs'

function readBoolMap(value: unknown): Record<string, boolean> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  const out: Record<string, boolean> = {}
  for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
    if (typeof key === 'string' && key.length > 0 && typeof entry === 'boolean') {
      out[key] = entry
    }
  }
  return out
}

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
          : undefined,
      expandedGroups: readBoolMap(entry.expandedGroups),
      expandedDirs: readBoolMap(entry.expandedDirs)
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

export function isMarkdown(path: string) {
  return /\.(md|mdx|markdown)$/i.test(path)
}

/** Workspace plan markdown under a `plans/` directory (matches server plan events). */
export function isPlansMarkdown(path: string) {
  const normalized = path.replace(/\\/g, '/')
  if (!/(^|\/)plans\//i.test(normalized)) return false
  return isMarkdown(normalized)
}

export function titleFromPlanPath(path: string) {
  const name = path.replace(/\\/g, '/').split('/').at(-1) || path
  const stem = name.replace(/\.(md|mdx|markdown)$/i, '')
  const titled = stem
    .split(/[-_]+/)
    .filter(Boolean)
    .join(' ')
  return titled.trim() || 'Plan'
}

export function isTextLike(path: string) {
  return /\.(json|md|mdx|markdown|txt|ya?ml|py|ts|tsx|js|jsx|css|html?|xml|cif|mmcif|pdb|sdf|jinja|jinja2|j2|toml)$/i.test(
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

/** Scaffold dirs created for every session — hide when empty. */
const SYSTEM_TOP_LEVEL_DIRS = new Set([
  'uploads',
  'outputs',
  'artifacts',
  'plans'
])

function artifactGroupKey(path: string): string {
  const parts = path.split('/').filter(Boolean)
  const top = parts[0]?.toLowerCase() || ''
  if (top === 'uploads') return 'Your uploads'
  if (top === 'outputs') return 'Generated outputs'
  if (top === 'project') return 'Project folder'
  if (parts.length > 1) return parts[0]
  return 'Artifacts'
}

function topLevelGroupKey(top: string): string {
  const key = top.toLowerCase()
  if (key === 'uploads') return 'Your uploads'
  if (key === 'outputs') return 'Generated outputs'
  if (key === 'project') return 'Project folder'
  return top
}

function ensureBucket(
  buckets: Map<string, WorkspaceFile[]>,
  key: string
): WorkspaceFile[] {
  const existing = buckets.get(key)
  if (existing) return existing
  const next: WorkspaceFile[] = []
  buckets.set(key, next)
  return next
}

/** Parent directory path for a workspace entry (`a/b/c` → `a/b`). */
export function parentDir(path: string): string {
  const parts = path.split('/').filter(Boolean)
  return parts.slice(0, -1).join('/')
}

/** Filesystem root path for an artifact group id/title. */
export function groupRootPath(groupId: string): string {
  if (groupId === 'Your uploads') return 'uploads'
  if (groupId === 'Generated outputs') return 'outputs'
  if (groupId === 'Project folder') return 'project'
  if (groupId === 'Artifacts') return ''
  return groupId
}

/** Newest-first by mtime; directories before files; name as tiebreaker. */
export function compareArtifacts(a: WorkspaceFile, b: WorkspaceFile): number {
  if (a.type !== b.type) return a.type === 'directory' ? -1 : 1
  const am = a.mtime ? new Date(a.mtime).getTime() : 0
  const bm = b.mtime ? new Date(b.mtime).getTime() : 0
  if (am !== bm) return bm - am
  return a.name.localeCompare(b.name)
}

/** Immediate children of `parentPath` within a flat listing. */
export function childrenOf(
  entries: WorkspaceFile[],
  parentPath: string
): WorkspaceFile[] {
  return entries
    .filter(entry => parentDir(entry.path) === parentPath)
    .sort(compareArtifacts)
}

export function groupArtifacts(entries: WorkspaceFile[]): ArtifactGroup[] {
  const buckets = new Map<string, WorkspaceFile[]>()

  for (const entry of entries) {
    const parts = entry.path.split('/').filter(Boolean)
    if (parts.length === 0) continue

    if (entry.type === 'directory') {
      if (parts.length === 1) {
        const top = parts[0]
        const key = topLevelGroupKey(top)
        // Always-present scaffold folders stay hidden until they have items.
        if (!SYSTEM_TOP_LEVEL_DIRS.has(top.toLowerCase())) {
          ensureBucket(buckets, key)
        }
        continue
      }
      ensureBucket(buckets, artifactGroupKey(entry.path)).push(entry)
      continue
    }

    ensureBucket(buckets, artifactGroupKey(entry.path)).push(entry)
  }

  const preferred = [
    'Project folder',
    'Your uploads',
    'Generated outputs',
    'Artifacts'
  ]
  const keys = [
    ...preferred.filter(key => buckets.has(key)),
    ...[...buckets.keys()].filter(key => !preferred.includes(key)).sort()
  ]
  return keys.map(title => ({
    id: title,
    title,
    files: (buckets.get(title) || []).sort(compareArtifacts)
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
