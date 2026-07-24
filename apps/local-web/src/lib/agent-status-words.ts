/** Realistic agent status copy driven by the active tool (not random fluff). */

export const DEFAULT_AGENT_STATUS = 'Planning next moves'

type StatusRule = {
  /** Match tool name (exact or prefix/includes). */
  match: string | RegExp
  label: string
}

const TOOL_STATUS_RULES: StatusRule[] = [
  { match: /^run_python$/i, label: 'Running Python' },
  { match: /^run_r$/i, label: 'Running R' },
  { match: /shell/i, label: 'Running shell command' },
  { match: /search_tools/i, label: 'Searching tools' },
  { match: /skills[._]?manage|skills_manage/i, label: 'Managing skills' },
  { match: /^read_file$/i, label: 'Reading file' },
  { match: /^write_file$/i, label: 'Writing file' },
  { match: /^edit_file$/i, label: 'Editing file' },
  { match: /write_todos/i, label: 'Updating plan' },
  { match: /sandbox_status/i, label: 'Checking sandbox' },
  { match: /sandbox_start/i, label: 'Starting sandbox' },
  { match: /sandbox_stop/i, label: 'Stopping sandbox' },
  { match: /pubmed|openalex|literature/i, label: 'Searching literature' },
  { match: /uniprot|opentargets|depmap|chembl/i, label: 'Querying databases' },
  { match: /geo_|omics\./i, label: 'Working with omics data' },
  { match: /chemistry|pubchem|descriptors/i, label: 'Analyzing chemistry' },
  { match: /pathway|expression|l1000/i, label: 'Analyzing expression' },
  { match: /clinical|trial/i, label: 'Checking clinical data' },
  { match: /genomics|gwas|coessential/i, label: 'Analyzing genomics' },
  { match: /safety|admet/i, label: 'Assessing safety' },
  { match: /web_search|browse|fetch_url/i, label: 'Browsing the web' },
  { match: /http|request|api/i, label: 'Calling an API' }
]

function normalizeToolName(name: string): string {
  return name.trim()
}

/** Human label for a tool name; falls back to a short generic line. */
export function statusLabelForTool(toolName: string | null | undefined): string {
  const name = normalizeToolName(toolName || '')
  if (!name) return DEFAULT_AGENT_STATUS
  for (const rule of TOOL_STATUS_RULES) {
    if (typeof rule.match === 'string') {
      if (name === rule.match || name.includes(rule.match)) return rule.label
      continue
    }
    if (rule.match.test(name)) return rule.label
  }
  const short = name.includes('.') ? name.split('.').pop() || name : name
  const pretty = short.replace(/_/g, ' ')
  return `Using ${pretty}`
}

export type StatusToolLike = {
  id?: string
  name: string
  status: 'pending' | 'completed' | 'error'
  startedAt?: string
}

function isNewerTool(candidate: StatusToolLike, current: StatusToolLike): boolean {
  const a = String(candidate.startedAt || '')
  const b = String(current.startedAt || '')
  if (a && b) return a >= b
  if (a && !b) return true
  if (!a && b) return false
  // No timestamps — treat later array order as newer (caller iterates in order).
  return true
}

/** Most recently started pending tool, or null. */
export function latestPendingTool(
  tools: StatusToolLike[] | null | undefined
): StatusToolLike | null {
  const list = tools || []
  let best: StatusToolLike | null = null
  for (const tool of list) {
    if (tool.status !== 'pending') continue
    if (!best || isNewerTool(tool, best)) best = tool
  }
  return best
}

/** Most recently started tool in the list (any status), or null. */
export function latestTool(
  tools: StatusToolLike[] | null | undefined
): StatusToolLike | null {
  const list = tools || []
  let best: StatusToolLike | null = null
  for (const tool of list) {
    if (!best || isNewerTool(tool, best)) best = tool
  }
  return best
}

/**
 * Pick status from the current run's tools.
 * Prefer the in-flight tool; otherwise mirror the newest tool card so the
 * label updates as soon as a card appears (even if it completes quickly).
 */
export function resolveAgentStatus(
  tools: StatusToolLike[] | null | undefined
): string {
  const pending = latestPendingTool(tools)
  if (pending) return statusLabelForTool(pending.name)
  const latest = latestTool(tools)
  if (latest) return statusLabelForTool(latest.name)
  return DEFAULT_AGENT_STATUS
}

/** Stable key so the status line remounts when the active tool changes. */
export function agentStatusKey(tools: StatusToolLike[] | null | undefined): string {
  const pending = latestPendingTool(tools)
  const active = pending || latestTool(tools)
  if (!active) return 'planning'
  return `${active.status}:${active.id || active.name}:${active.startedAt || ''}`
}
