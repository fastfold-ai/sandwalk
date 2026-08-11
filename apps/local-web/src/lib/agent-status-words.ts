/** Realistic agent status copy driven by the active tool (not random fluff). */

export const DEFAULT_AGENT_STATUS = 'Planning next moves'
export const WAITING_ON_MODEL_STATUS = 'Waiting on the model provider'
export const MODEL_SLOW_STATUS = 'Model provider is taking longer than usual'

/** Quiet gap before we hint the model is still thinking. */
export const WAITING_ON_MODEL_AFTER_MS = 15_000
/** Longer quiet gap for a stronger “still waiting” hint. */
export const MODEL_SLOW_AFTER_MS = 45_000

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

/**
 * Pick status from the current run's tools and quiet-time gap.
 * Prefer the in-flight tool; otherwise escalate from planning → waiting → slow
 * when the model has been silent for a while.
 */
export function resolveAgentStatus(
  tools: StatusToolLike[] | null | undefined,
  options?: { quietMs?: number }
): string {
  const pending = latestPendingTool(tools)
  if (pending) return statusLabelForTool(pending.name)
  const quietMs = Math.max(0, options?.quietMs ?? 0)
  if (quietMs >= MODEL_SLOW_AFTER_MS) return MODEL_SLOW_STATUS
  if (quietMs >= WAITING_ON_MODEL_AFTER_MS) return WAITING_ON_MODEL_STATUS
  return DEFAULT_AGENT_STATUS
}

/** Stable key so the status line remounts when the active tool / wait phase changes. */
export function agentStatusKey(
  tools: StatusToolLike[] | null | undefined,
  options?: { quietMs?: number }
): string {
  const pending = latestPendingTool(tools)
  if (pending) {
    return `${pending.status}:${pending.id || pending.name}:${pending.startedAt || ''}`
  }
  const label = resolveAgentStatus(tools, options)
  if (label === MODEL_SLOW_STATUS) return 'model-slow'
  if (label === WAITING_ON_MODEL_STATUS) return 'waiting-on-model'
  return 'planning'
}
