import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  Automation,
  AutomationRun,
  AutomationSessionMode,
  AutomationTemplate,
  McpServer,
  Specialist,
  SshHost
} from '@sandwalk/agent-ui-core'
import {
  ArrowLeft,
  Bot,
  Brain,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  Copy,
  FolderGit2,
  Loader2,
  Play,
  Plus,
  Search,
  Server,
  Sparkles,
  Trash2,
  Webhook
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { SpecialistAvatar } from '@/components/agents/specialists-view/specialist-ui'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'

function Switch({
  checked,
  onCheckedChange
}: {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none',
        checked ? 'bg-emerald-500' : 'bg-muted-foreground/30'
      )}
    >
      <span
        className={cn(
          'bg-background pointer-events-none block size-4 rounded-full shadow-sm transition-transform',
          checked ? 'translate-x-4' : 'translate-x-0'
        )}
      />
    </button>
  )
}

const SCHEDULE_PRESETS = [
  { label: 'Every 15 minutes', expr: 'every 15m' },
  { label: 'Hourly', expr: 'every 1h' },
  { label: 'Daily at 9:00 AM', expr: 'daily at 9:00am' },
  { label: 'Weekdays at 8:30 AM', expr: 'weekdays at 8:30am' },
  { label: 'Weekly (Mondays 9:00 AM)', expr: 'every monday at 9:00am' },
  { label: 'One-shot in 30m', expr: 'in 30m' },
  { label: 'Webhook Triggered', expr: 'webhook' }
] as const

const AVAILABLE_SKILLS = [
  'automate',
  'knowledge-steward',
  'omnigraph',
  'boltz',
  'diagrams_mermaid',
  'slack_report',
  'ssh',
  'tao-run-on-slurm'
] as const

const AUTOMATIONS_PAGE_SIZE = 5
const RUNS_PAGE_SIZE = 6

export function AutomationsView({
  client,
  projects,
  specialists
}: {
  client: LocalAgentClient
  projects: AgentProject[]
  specialists: Specialist[]
}) {
  const navigate = useNavigate()
  const [subTab, setSubTab] = useState<'automations' | 'runs'>('automations')
  const [automations, setAutomations] = useState<Automation[]>([])
  const [templates, setTemplates] = useState<AutomationTemplate[]>([])
  const [runs, setRuns] = useState<AutomationRun[]>([])
  const [sshHosts, setSshHosts] = useState<SshHost[]>([])
  const [mcpServers, setMcpServers] = useState<McpServer[]>([])
  const [loading, setLoading] = useState(true)

  // Search & Pagination state
  const [searchQuery, setSearchQuery] = useState('')
  const [automationsPage, setAutomationsPage] = useState(1)
  const [runsPage, setRunsPage] = useState(1)

  // Editor state (`null` = Hub view, `'new'` or automation ID = Editor view)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editorTab, setEditorTab] = useState<'settings' | 'history'>('settings')
  const [skillsPickerOpen, setSkillsPickerOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testingRun, setTestingRun] = useState(false)

  // Editor form fields
  const [draftName, setDraftName] = useState('Untitled')
  const [draftEnabled, setDraftEnabled] = useState(true)
  const [draftScheduleExpr, setDraftScheduleExpr] = useState('every 1h')
  const [draftSessionMode, setDraftSessionMode] =
    useState<AutomationSessionMode>('fresh')
  const [draftPrompt, setDraftPrompt] = useState('')
  const [draftCommand, setDraftCommand] = useState('')
  const [draftSpecialistId, setDraftSpecialistId] = useState<string>('')
  const [draftTargetValue, setDraftTargetValue] = useState<string>('none')
  const [draftWorkdir, setDraftWorkdir] = useState<string>('')
  const [draftSkills, setDraftSkills] = useState<string[]>([])
  const [draftMcpIds, setDraftMcpIds] = useState<string[]>([])
  const [draftContinuity, setDraftContinuity] = useState(true)
  const [draftWakeOnChange, setDraftWakeOnChange] = useState(false)
  const [draftWebhookToken, setDraftWebhookToken] = useState<string | null>(
    null
  )

  const refreshAll = useCallback(async () => {
    try {
      const [autoList, tplList, runList, hostList, mcpList] = await Promise.all([
        client.listAutomations().catch(() => []),
        client.listAutomationTemplates().catch(() => []),
        client.listAutomationRuns({ limit: 100 }).catch(() => []),
        client.listSshHosts(true).catch(() => []),
        client.listMcpServers().catch(() => [])
      ])
      setAutomations(autoList)
      setTemplates(tplList)
      setRuns(runList)
      setSshHosts(hostList)
      setMcpServers(mcpList)
    } finally {
      setLoading(false)
    }
  }, [client])

  useEffect(() => {
    void refreshAll()
  }, [refreshAll])

  const openEditorForNew = useCallback(
    (tpl?: AutomationTemplate) => {
      setEditingId('new')
      setEditorTab('settings')
      setSkillsPickerOpen(false)
      setDraftName(tpl ? tpl.name : 'Untitled')
      setDraftEnabled(true)
      setDraftScheduleExpr(tpl ? tpl.scheduleExpr : 'every 1h')
      setDraftSessionMode(tpl ? tpl.sessionMode : 'fresh')
      setDraftPrompt(tpl ? tpl.prompt : '')
      setDraftCommand(tpl?.command || '')
      const recSpec = tpl?.recommendedSpecialistSlug
        ? specialists.find(s => s.slug === tpl.recommendedSpecialistSlug)
        : null
      setDraftSpecialistId(recSpec?.id || '')
      if (tpl?.category === 'hpc_slurm' && sshHosts.length > 0) {
        setDraftTargetValue(`ssh:${sshHosts[0].id}`)
        setDraftWorkdir(sshHosts[0].defaultWorkdir || '')
      } else {
        setDraftTargetValue('none')
        setDraftWorkdir('')
      }
      setDraftSkills(tpl ? [...tpl.skillNames] : [])
      setDraftMcpIds([])
      setDraftContinuity(tpl ? tpl.continuity : true)
      setDraftWakeOnChange(tpl ? tpl.wakeOnChangeOnly : false)
      setDraftWebhookToken(null)
    },
    [specialists, sshHosts]
  )

  const openEditorForExisting = useCallback((item: Automation) => {
    setEditingId(item.id)
    setEditorTab('settings')
    setSkillsPickerOpen(false)
    setDraftName(item.name)
    setDraftEnabled(item.enabled)
    setDraftScheduleExpr(item.scheduleExpr)
    setDraftSessionMode(item.sessionMode)
    setDraftPrompt(item.prompt)
    setDraftCommand(item.command || '')
    setDraftSpecialistId(item.specialistId || '')
    if (item.sshHostId) {
      setDraftTargetValue(`ssh:${item.sshHostId}`)
      setDraftWorkdir(item.remoteWorkdir || '')
    } else if (item.projectId) {
      setDraftTargetValue(`project:${item.projectId}`)
      setDraftWorkdir(item.workdir || '')
    } else {
      setDraftTargetValue('none')
      setDraftWorkdir(item.workdir || '')
    }
    setDraftSkills(item.skillNames || [])
    setDraftMcpIds(item.mcpServerIds || [])
    setDraftContinuity(item.continuity)
    setDraftWakeOnChange(item.wakeOnChangeOnly)
    setDraftWebhookToken(item.webhookToken || null)
  }, [])

  const parseTargetSelection = () => {
    if (draftTargetValue.startsWith('ssh:')) {
      return {
        sshHostId: draftTargetValue.slice(4),
        projectId: null,
        remoteWorkdir: draftWorkdir.trim() || null,
        workdir: null
      }
    }
    if (draftTargetValue.startsWith('project:')) {
      return {
        sshHostId: null,
        projectId: draftTargetValue.slice(8),
        remoteWorkdir: null,
        workdir: draftWorkdir.trim() || null
      }
    }
    return {
      sshHostId: null,
      projectId: null,
      remoteWorkdir: null,
      workdir: draftWorkdir.trim() || null
    }
  }

  const saveAutomation = async () => {
    setSaving(true)
    try {
      const tgt = parseTargetSelection()
      if (editingId === 'new') {
        const created = await client.createAutomation({
          name: draftName.trim() || 'Untitled automation',
          prompt: draftPrompt,
          command: draftCommand.trim() || null,
          scheduleExpr: draftScheduleExpr.trim() || 'every 1h',
          sessionMode: draftSessionMode,
          specialistId: draftSpecialistId || null,
          projectId: tgt.projectId,
          workdir: tgt.workdir,
          sshHostId: tgt.sshHostId,
          remoteWorkdir: tgt.remoteWorkdir,
          skillNames: draftSkills,
          mcpServerIds: draftMcpIds,
          continuity: draftContinuity,
          wakeOnChangeOnly: draftWakeOnChange,
          enabled: draftEnabled
        })
        toast.success(`Saved automation "${created.name}"`)
        await refreshAll()
        openEditorForExisting(created)
      } else if (editingId) {
        const updated = await client.updateAutomation(editingId, {
          name: draftName.trim() || 'Untitled automation',
          prompt: draftPrompt,
          command: draftCommand.trim() || null,
          clearCommand: !draftCommand.trim(),
          scheduleExpr: draftScheduleExpr.trim() || 'every 1h',
          sessionMode: draftSessionMode,
          specialistId: draftSpecialistId || null,
          clearSpecialistId: !draftSpecialistId,
          projectId: tgt.projectId,
          clearProjectId: !tgt.projectId,
          workdir: tgt.workdir,
          clearWorkdir: !tgt.workdir,
          sshHostId: tgt.sshHostId,
          clearSshHostId: !tgt.sshHostId,
          remoteWorkdir: tgt.remoteWorkdir,
          clearRemoteWorkdir: !tgt.remoteWorkdir,
          skillNames: draftSkills,
          mcpServerIds: draftMcpIds,
          continuity: draftContinuity,
          wakeOnChangeOnly: draftWakeOnChange,
          enabled: draftEnabled
        })
        toast.success(`Updated "${updated.name}"`)
        await refreshAll()
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Could not save automation'
      )
    } finally {
      setSaving(false)
    }
  }

  const testRunCurrent = async () => {
    setTestingRun(true)
    try {
      let targetId = editingId
      const tgt = parseTargetSelection()
      if (targetId === 'new') {
        const created = await client.createAutomation({
          name: draftName.trim() || 'Untitled automation',
          prompt: draftPrompt,
          command: draftCommand.trim() || null,
          scheduleExpr: draftScheduleExpr.trim() || 'every 1h',
          sessionMode: draftSessionMode,
          specialistId: draftSpecialistId || null,
          projectId: tgt.projectId,
          workdir: tgt.workdir,
          sshHostId: tgt.sshHostId,
          remoteWorkdir: tgt.remoteWorkdir,
          skillNames: draftSkills,
          mcpServerIds: draftMcpIds,
          continuity: draftContinuity,
          wakeOnChangeOnly: draftWakeOnChange,
          enabled: draftEnabled
        })
        targetId = created.id
        setEditingId(created.id)
      }
      if (!targetId) return
      const run = await client.triggerAutomation(targetId, { wait: true })
      toast.success(`Test run finished (${run.status})`)
      await refreshAll()
      setEditorTab('history')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Test run failed')
    } finally {
      setTestingRun(false)
    }
  }

  const filteredAutomations = useMemo(() => {
    return automations.filter(a => {
      if (!searchQuery.trim()) return true
      const q = searchQuery.toLowerCase()
      return (
        a.name.toLowerCase().includes(q) ||
        (a.prompt || '').toLowerCase().includes(q) ||
        a.scheduleLabel.toLowerCase().includes(q)
      )
    })
  }, [automations, searchQuery])

  const totalAutomationPages = Math.max(
    1,
    Math.ceil(filteredAutomations.length / AUTOMATIONS_PAGE_SIZE)
  )
  const pagedAutomations = useMemo(() => {
    const start = (automationsPage - 1) * AUTOMATIONS_PAGE_SIZE
    return filteredAutomations.slice(start, start + AUTOMATIONS_PAGE_SIZE)
  }, [filteredAutomations, automationsPage])

  const totalRunPages = Math.max(1, Math.ceil(runs.length / RUNS_PAGE_SIZE))
  const pagedRuns = useMemo(() => {
    const start = (runsPage - 1) * RUNS_PAGE_SIZE
    return runs.slice(start, start + RUNS_PAGE_SIZE)
  }, [runs, runsPage])

  const editingRuns = useMemo(() => {
    if (!editingId || editingId === 'new') return []
    return runs.filter(r => r.automationId === editingId)
  }, [runs, editingId])

  // ============================================================================
  // RENDER: Screen 2 — Minimal Generic Automation Editor (`Automations > Untitled`)
  // ============================================================================
  if (editingId !== null) {
    const selectedSpec = specialists.find(s => s.id === draftSpecialistId)

    return (
      <div className="mx-auto flex h-full w-full max-w-7xl flex-col px-4 pt-6 pb-8 md:px-6 md:pt-8">
        {/* Top Breadcrumb & Action Bar */}
        <div className="mb-6 flex items-center justify-between gap-4 border-b pb-3.5">
          <div className="flex items-center gap-2 text-sm">
            <button
              type="button"
              onClick={() => setEditingId(null)}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <ArrowLeft className="size-3.5" />
              Automations
            </button>
            <ChevronRight className="text-muted-foreground/60 size-3.5" />
            <span className="text-foreground font-medium">
              {draftName || 'Untitled'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {editingId !== 'new' ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-destructive h-8 px-2.5"
                onClick={async () => {
                  await client.deleteAutomation(editingId)
                  toast.success('Deleted automation')
                  setEditingId(null)
                  await refreshAll()
                }}
              >
                <Trash2 className="size-3.5" />
              </Button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 gap-1.5"
              disabled={testingRun || saving}
              onClick={() => void testRunCurrent()}
            >
              {testingRun ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Play className="size-3.5" />
              )}
              Test
            </Button>
            <Button
              type="button"
              size="sm"
              className="h-8 gap-1.5"
              disabled={saving}
              onClick={() => void saveAutomation()}
            >
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : null}
              Save
            </Button>
          </div>
        </div>

        {/* Title & Compact Context Row */}
        <div className="mb-5 space-y-3">
          <input
            type="text"
            value={draftName}
            onChange={e => setDraftName(e.target.value)}
            placeholder="Untitled"
            className="text-foreground placeholder:text-muted-foreground/50 w-full bg-transparent text-2xl font-semibold tracking-tight outline-none"
          />

          <div className="text-muted-foreground flex flex-wrap items-center gap-3 text-xs">
            <label className="inline-flex cursor-pointer items-center gap-2">
              <Switch
                checked={draftEnabled}
                onCheckedChange={setDraftEnabled}
              />
              <span
                className={cn(
                  'font-medium',
                  draftEnabled ? 'text-emerald-400' : 'text-muted-foreground'
                )}
              >
                {draftEnabled ? 'Active' : 'Inactive'}
              </span>
            </label>

            <span>·</span>

            <div className="inline-flex items-center gap-1.5">
              <FolderGit2 className="size-3.5" />
              <select
                value={draftTargetValue}
                onChange={e => {
                  const val = e.target.value
                  setDraftTargetValue(val)
                  if (val.startsWith('ssh:')) {
                    const h = sshHosts.find(item => item.id === val.slice(4))
                    if (h?.defaultWorkdir) setDraftWorkdir(h.defaultWorkdir)
                  }
                }}
                className="bg-muted/50 text-foreground rounded-md border px-2 py-1 text-xs outline-none"
              >
                <option value="none">Select workspace</option>
                {projects.length > 0 ? (
                  <optgroup label="Projects">
                    {projects.map(p => (
                      <option key={p.id} value={`project:${p.id}`}>
                        {p.name}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
                {sshHosts.length > 0 ? (
                  <optgroup label="SSH Servers">
                    {sshHosts.map(h => (
                      <option key={h.id} value={`ssh:${h.id}`}>
                        SSH: {h.alias} ({h.host})
                      </option>
                    ))}
                  </optgroup>
                ) : null}
              </select>
            </div>

            <span>·</span>

            <div className="inline-flex items-center gap-1.5">
              <span>Agent:</span>
              <select
                value={draftSpecialistId}
                onChange={e => setDraftSpecialistId(e.target.value)}
                className="bg-muted/50 text-foreground rounded-md border px-2 py-1 text-xs outline-none"
              >
                <option value="">Default Agent</option>
                {specialists.map(sp => (
                  <option key={sp.id} value={sp.id}>
                    {sp.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Settings | Run History Sub-tabs */}
        <div className="mb-5 flex items-center gap-4 border-b text-xs font-medium">
          <button
            type="button"
            onClick={() => setEditorTab('settings')}
            className={cn(
              '-mb-px border-b-2 pb-2.5 transition-colors',
              editorTab === 'settings'
                ? 'border-foreground text-foreground'
                : 'text-muted-foreground hover:text-foreground border-transparent'
            )}
          >
            Settings
          </button>
          <button
            type="button"
            onClick={() => setEditorTab('history')}
            className={cn(
              '-mb-px border-b-2 pb-2.5 transition-colors',
              editorTab === 'history'
                ? 'border-foreground text-foreground'
                : 'text-muted-foreground hover:text-foreground border-transparent'
            )}
          >
            Run History ({editingRuns.length})
          </button>
        </div>

        {editorTab === 'settings' ? (
          <div className="chat-scrollbar flex-1 space-y-4 overflow-y-auto pr-1 pb-8">
            {/* 1. Triggers */}
            <section className="space-y-1.5">
              <p className="text-muted-foreground text-xs font-medium">
                Triggers
              </p>
              <div className="border-border/60 bg-card/40 flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
                <div className="flex items-center gap-2.5">
                  <Clock className="text-muted-foreground size-4" />
                  <select
                    aria-label="When to run"
                    value={
                      SCHEDULE_PRESETS.some(p => p.expr === draftScheduleExpr)
                        ? draftScheduleExpr
                        : 'custom'
                    }
                    onChange={e => {
                      if (e.target.value !== 'custom') {
                        setDraftScheduleExpr(e.target.value)
                      }
                    }}
                    className="bg-muted/60 text-foreground h-8 rounded-md border px-2.5 text-xs outline-none"
                  >
                    {SCHEDULE_PRESETS.map(p => (
                      <option key={p.expr} value={p.expr}>
                        {p.label}
                      </option>
                    ))}
                    <option value="custom">Custom (cron)</option>
                  </select>
                  <Input
                    value={draftScheduleExpr}
                    onChange={e => setDraftScheduleExpr(e.target.value)}
                    placeholder="every 1h or 0 9 * * 1-5"
                    className="h-8 w-44 font-mono text-xs"
                  />
                </div>

                {draftWebhookToken ? (
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 font-mono text-[11px]"
                    onClick={() => {
                      void copyText(
                        `curl -fsS -X POST http://127.0.0.1:8787/v1/automations/webhook/${draftWebhookToken}`
                      )
                      toast.success('Copied webhook URL')
                    }}
                  >
                    <Webhook className="size-3.5" />
                    Webhook
                    <Copy className="size-3" />
                  </button>
                ) : null}
              </div>
            </section>

            {/* 2. Prompt / Instructions */}
            <section className="space-y-1.5">
              <div className="flex items-center justify-between">
                <p className="text-muted-foreground text-xs font-medium">
                  Instructions
                </p>
                <div className="bg-muted/50 inline-flex rounded-lg p-0.5 text-xs">
                  {(
                    [
                      { id: 'fresh', label: 'New Session' },
                      { id: 'continue', label: 'Same Thread' },
                      { id: 'no_agent', label: 'Script Only' }
                    ] as const
                  ).map(m => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setDraftSessionMode(m.id)}
                      className={cn(
                        'rounded-md px-2.5 py-1 text-[11px] transition-colors',
                        draftSessionMode === m.id
                          ? 'bg-background text-foreground font-medium shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>

              {draftSessionMode !== 'no_agent' ? (
                <textarea
                  value={draftPrompt}
                  onChange={e => setDraftPrompt(e.target.value)}
                  rows={6}
                  placeholder={`Write instructions for ${selectedSpec?.name || 'the agent'}...`}
                  className="border-border/60 bg-card/40 placeholder:text-muted-foreground/60 w-full rounded-xl border p-3.5 text-sm leading-relaxed outline-none focus:ring-1"
                />
              ) : (
                <Input
                  value={draftCommand}
                  onChange={e => setDraftCommand(e.target.value)}
                  placeholder="Shell command to run on schedule..."
                  className="font-mono text-xs"
                />
              )}
            </section>

            {/* 3. Memories Row */}
            <section className="border-border/60 bg-card/40 flex items-center justify-between rounded-xl border px-3.5 py-2.5">
              <div className="flex items-center gap-2 text-xs">
                <Brain className="text-muted-foreground size-4" />
                <span className="font-medium">Memories</span>
                <span className="text-muted-foreground hidden sm:inline">
                  · Remember previous run output so reports don’t repeat
                </span>
              </div>
              <div className="flex items-center gap-2.5">
                <Switch
                  checked={draftContinuity}
                  onCheckedChange={setDraftContinuity}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => navigate('/dashboard/memory')}
                >
                  Manage
                </Button>
              </div>
            </section>

            {/* 4. Compact `+ Add Tool, Skill or MCP` Row */}
            <section className="border-border/60 bg-card/40 space-y-2.5 rounded-xl border px-3.5 py-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => setSkillsPickerOpen(v => !v)}
                  className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs font-medium"
                >
                  <Plus className="size-3.5" />
                  Add Tool, Skill or MCP
                </button>
                <div className="flex flex-wrap items-center gap-1.5">
                  {selectedSpec ? (
                    <span className="text-muted-foreground text-[11px]">
                      Inherits {selectedSpec.name}’s active MCPs & tools
                    </span>
                  ) : null}
                  {draftSkills.map(sk => (
                    <span
                      key={sk}
                      className="border-emerald-500/40 bg-emerald-500/10 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] text-emerald-300"
                    >
                      /{sk}
                    </span>
                  ))}
                  {draftMcpIds.map(mid => {
                    const srv = mcpServers.find(m => m.id === mid)
                    return (
                      <span
                        key={mid}
                        className="border-blue-500/40 bg-blue-500/10 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] text-blue-300"
                      >
                        MCP: {srv?.name || mid}
                      </span>
                    )
                  })}
                </div>
              </div>

              {skillsPickerOpen ? (
                <div className="space-y-2.5 border-t pt-2.5">
                  <div className="flex flex-wrap gap-1.5">
                    {AVAILABLE_SKILLS.map(sk => {
                      const active = draftSkills.includes(sk)
                      return (
                        <button
                          key={sk}
                          type="button"
                          onClick={() =>
                            setDraftSkills(curr =>
                              curr.includes(sk)
                                ? curr.filter(x => x !== sk)
                                : [...curr, sk]
                            )
                          }
                          className={cn(
                            'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors',
                            active
                              ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-300'
                              : 'text-muted-foreground hover:text-foreground'
                          )}
                        >
                          <Sparkles className="size-3" />/{sk}
                          {active ? <Check className="size-3" /> : null}
                        </button>
                      )
                    })}
                  </div>
                  {mcpServers.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-1.5 border-t pt-2">
                      <span className="text-muted-foreground mr-1 text-[11px]">
                        MCP Servers:
                      </span>
                      {mcpServers.map(srv => {
                        const active = draftMcpIds.includes(srv.id)
                        return (
                          <button
                            key={srv.id}
                            type="button"
                            onClick={() =>
                              setDraftMcpIds(curr =>
                                curr.includes(srv.id)
                                  ? curr.filter(x => x !== srv.id)
                                  : [...curr, srv.id]
                              )
                            }
                            className={cn(
                              'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors',
                              active
                                ? 'border-blue-500/50 bg-blue-500/15 text-blue-300'
                                : 'text-muted-foreground hover:text-foreground'
                            )}
                          >
                            MCP: {srv.name}
                            {active ? <Check className="size-3" /> : null}
                          </button>
                        )
                      })}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>
          </div>
        ) : (
          /* Run History Tab */
          <div className="chat-scrollbar flex-1 space-y-2.5 overflow-y-auto pb-8">
            {editingRuns.length === 0 ? (
              <div className="border-border/50 text-muted-foreground rounded-xl border border-dashed p-8 text-center text-sm">
                No runs recorded yet. Click <strong>Test</strong> in the top
                right to run this automation now.
              </div>
            ) : (
              editingRuns.map(r => (
                <div
                  key={r.id}
                  className="border-border/60 bg-card/40 flex flex-col gap-2 rounded-xl border p-3.5"
                >
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'inline-block size-2 rounded-full',
                          r.status === 'succeeded'
                            ? 'bg-emerald-400'
                            : r.status === 'failed'
                              ? 'bg-rose-400'
                              : 'bg-amber-400'
                        )}
                      />
                      <span className="font-medium capitalize">{r.status}</span>
                      <span className="text-muted-foreground">
                        · {new Date(r.startedAt).toLocaleString()}
                      </span>
                      {r.durationSeconds != null ? (
                        <span className="text-muted-foreground">
                          ({r.durationSeconds.toFixed(1)}s)
                        </span>
                      ) : null}
                    </div>
                    {r.sessionId ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => navigate(`/agents/${r.sessionId}`)}
                      >
                        Open Session
                      </Button>
                    ) : null}
                  </div>
                  {r.outputExcerpt || r.error ? (
                    <pre className="bg-muted/40 text-muted-foreground max-h-40 overflow-auto rounded-lg p-2.5 font-mono text-[11px] whitespace-pre-wrap">
                      {r.error || r.outputExcerpt}
                    </pre>
                  ) : null}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    )
  }

  // ============================================================================
  // RENDER: Screen 1 — Clean Automations Hub (with Pagination)
  // ============================================================================
  return (
    <div className="mx-auto flex h-full w-full max-w-7xl flex-col px-4 pt-6 pb-8 md:px-6 md:pt-8">
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Automations</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Automate repetitive tasks with scheduled and event-driven agents.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 text-xs"
            onClick={() =>
              setSubTab(curr => (curr === 'runs' ? 'automations' : 'runs'))
            }
          >
            {subTab === 'runs'
              ? 'Back to Automations'
              : `Run History (${runs.length})`}
          </Button>
          <Button
            type="button"
            size="sm"
            className="h-8 gap-1.5 rounded-full px-3.5"
            onClick={() => openEditorForNew()}
          >
            <Plus className="size-3.5" />
            New Automation
          </Button>
        </div>
      </div>

      {subTab === 'automations' ? (
        <div className="chat-scrollbar flex-1 space-y-8 overflow-y-auto pr-1 pb-10">
          {/* Active Automations Table */}
          <section className="space-y-2.5">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                Your Automations ({filteredAutomations.length})
              </h2>
              {automations.length > 3 ? (
                <div className="relative">
                  <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" />
                  <Input
                    value={searchQuery}
                    onChange={e => {
                      setSearchQuery(e.target.value)
                      setAutomationsPage(1)
                    }}
                    placeholder="Search..."
                    className="h-7 w-48 pl-8 text-xs"
                  />
                </div>
              ) : null}
            </div>

            <div className="border-border/60 bg-card/30 overflow-hidden rounded-xl border">
              {loading ? (
                <div className="text-muted-foreground p-6 text-center text-xs">
                  Loading automations...
                </div>
              ) : pagedAutomations.length === 0 ? (
                <div className="text-muted-foreground p-6 text-center text-xs">
                  No automations yet. Click <strong>New Automation</strong> or
                  start from a template below.
                </div>
              ) : (
                pagedAutomations.map(item => {
                  const spec = specialists.find(s => s.id === item.specialistId)
                  const ssh = sshHosts.find(h => h.id === item.sshHostId)
                  return (
                    <div
                      key={item.id}
                      onClick={() => openEditorForExisting(item)}
                      className="border-border/40 hover:bg-muted/30 flex cursor-pointer items-center justify-between gap-4 border-b px-4 py-3 text-xs transition-colors last:border-b-0"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        {spec ? (
                          <SpecialistAvatar
                            color={spec.color}
                            icon={spec.icon}
                            size="sm"
                            className="size-6"
                          />
                        ) : (
                          <Bot className="text-muted-foreground size-4 shrink-0" />
                        )}
                        <div className="min-w-0">
                          <p className="text-foreground truncate font-medium">
                            {item.name}
                          </p>
                          <p className="text-muted-foreground truncate text-[11px]">
                            {item.scheduleLabel} ·{' '}
                            {ssh
                              ? `SSH: ${ssh.alias}`
                              : item.workdir || 'Local workspace'}
                          </p>
                        </div>
                      </div>

                      <div
                        className="flex shrink-0 items-center gap-3"
                        onClick={e => e.stopPropagation()}
                      >
                        <span
                          className={cn(
                            'inline-flex items-center gap-1.5 text-xs',
                            item.enabled
                              ? 'text-emerald-400'
                              : 'text-muted-foreground'
                          )}
                        >
                          <span
                            className={cn(
                              'size-1.5 rounded-full',
                              item.enabled
                                ? 'bg-emerald-400'
                                : 'bg-muted-foreground/50'
                            )}
                          />
                          {item.enabled ? 'Active' : 'Paused'}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          title="Run now"
                          onClick={async () => {
                            await client.triggerAutomation(item.id, {
                              wait: true
                            })
                            toast.success(`Triggered "${item.name}"`)
                            await refreshAll()
                          }}
                        >
                          <Play className="size-3.5" />
                        </Button>
                        <Switch
                          checked={item.enabled}
                          onCheckedChange={async checked => {
                            await client.updateAutomation(item.id, {
                              enabled: checked
                            })
                            await refreshAll()
                          }}
                        />
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {totalAutomationPages > 1 ? (
              <div className="text-muted-foreground flex items-center justify-end gap-2 pt-1 text-xs">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2"
                  disabled={automationsPage <= 1}
                  onClick={() => setAutomationsPage(p => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="size-3.5" />
                  Previous
                </Button>
                <span>
                  Page {automationsPage} of {totalAutomationPages}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2"
                  disabled={automationsPage >= totalAutomationPages}
                  onClick={() =>
                    setAutomationsPage(p =>
                      Math.min(totalAutomationPages, p + 1)
                    )
                  }
                >
                  Next
                  <ChevronRight className="size-3.5" />
                </Button>
              </div>
            ) : null}
          </section>

          {/* Starter Templates Grid */}
          <section className="space-y-2.5">
            <h2 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              Templates
            </h2>

            <div className="grid grid-cols-1 gap-3.5 md:grid-cols-3">
              {templates.map(tpl => {
                const tplSpec = tpl.recommendedSpecialistSlug
                  ? specialists.find(
                      s => s.slug === tpl.recommendedSpecialistSlug
                    )
                  : null
                const hasNvidiaSlurm =
                  tpl.skillNames?.includes('tao-run-on-slurm')
                return (
                  <div
                    key={tpl.id}
                    className="border-border/60 bg-card/40 hover:border-border flex flex-col justify-between rounded-xl border p-4 transition-all"
                  >
                    <div>
                      <div className="mb-2.5 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {tplSpec ? (
                            <SpecialistAvatar
                              color={tplSpec.color}
                              icon={tplSpec.icon}
                              size="sm"
                              className="size-7"
                            />
                          ) : (
                            <span className="bg-primary/15 text-primary inline-flex size-7 items-center justify-center overflow-hidden rounded-lg">
                              {tpl.category === 'environment' ? (
                                <Server className="size-3.5" />
                              ) : tpl.category === 'bio_compchem' ? (
                                <Sparkles className="size-3.5" />
                              ) : (
                                <Bot className="size-3.5" />
                              )}
                            </span>
                          )}
                          {hasNvidiaSlurm ? (
                            <img
                              src="/suggestions/nvidia.png"
                              alt="NVIDIA Slurm"
                              className="size-5 rounded-md object-cover"
                            />
                          ) : null}
                        </div>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          className="h-7 rounded-lg px-2.5 text-xs"
                          onClick={() => openEditorForNew(tpl)}
                        >
                          Use
                        </Button>
                      </div>
                      <h3 className="text-foreground text-sm font-medium">
                        {tpl.name}
                      </h3>
                      <p className="text-muted-foreground mt-1 line-clamp-2 text-xs leading-relaxed">
                        {tpl.description}
                      </p>
                    </div>

                    <div className="text-muted-foreground mt-3.5 flex items-center gap-1.5 overflow-hidden border-t pt-2.5 text-[11px]">
                      <Clock className="size-3 shrink-0" />
                      <span
                        className="shrink-0"
                        style={{ whiteSpace: 'nowrap' }}
                      >
                        {tpl.scheduleLabel.replace(/\s+(AM|PM)\b/, '\u00A0$1')}
                      </span>
                      <span className="shrink-0">→</span>
                      <span className="text-foreground/80 min-w-0 truncate font-medium">
                        {tplSpec
                          ? `${tplSpec.name} · ${tpl.badge.replace(/^Scheduled\s*·\s*/i, '')}`
                          : tpl.badge}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>
        </div>
      ) : (
        /* Paginated Run History View */
        <div className="chat-scrollbar flex-1 space-y-3 overflow-y-auto pb-10">
          {pagedRuns.length === 0 ? (
            <div className="text-muted-foreground p-8 text-center text-sm">
              No automation runs yet.
            </div>
          ) : (
            pagedRuns.map(r => {
              const parentAuto = automations.find(a => a.id === r.automationId)
              const runSpec = parentAuto?.specialistId
                ? specialists.find(s => s.id === parentAuto.specialistId)
                : null
              return (
                <div
                  key={r.id}
                  className="border-border/60 bg-card/40 flex items-center justify-between gap-4 rounded-xl border p-3.5 text-xs"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    {runSpec ? (
                      <SpecialistAvatar
                        color={runSpec.color}
                        icon={runSpec.icon}
                        size="sm"
                        className="size-6 shrink-0"
                      />
                    ) : (
                      <Bot className="text-muted-foreground size-4 shrink-0" />
                    )}
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={cn(
                            'size-2 rounded-full',
                            r.status === 'succeeded'
                              ? 'bg-emerald-400'
                              : r.status === 'failed'
                                ? 'bg-rose-400'
                                : 'bg-amber-400'
                          )}
                        />
                        <span className="font-medium">
                          {r.automationName || r.automationId}
                        </span>
                        {runSpec ? (
                          <span className="text-muted-foreground">
                            · {runSpec.name}
                          </span>
                        ) : null}
                        <span className="text-muted-foreground capitalize">
                          · {r.status}
                        </span>
                        <span className="text-muted-foreground">
                          · {new Date(r.startedAt).toLocaleString()}
                        </span>
                      </div>
                      {r.outputExcerpt || r.error ? (
                        <p className="text-muted-foreground line-clamp-1 font-mono text-[11px]">
                          {r.error || r.outputExcerpt}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  {r.sessionId ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 shrink-0 text-xs"
                      onClick={() => navigate(`/agents/${r.sessionId}`)}
                    >
                      Open Session
                    </Button>
                  ) : null}
                </div>
              )
            })
          )}

          {totalRunPages > 1 ? (
            <div className="text-muted-foreground flex items-center justify-end gap-2 pt-2 text-xs">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2"
                disabled={runsPage <= 1}
                onClick={() => setRunsPage(p => Math.max(1, p - 1))}
              >
                <ChevronLeft className="size-3.5" />
                Previous
              </Button>
              <span>
                Page {runsPage} of {totalRunPages}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2"
                disabled={runsPage >= totalRunPages}
                onClick={() =>
                  setRunsPage(p => Math.min(totalRunPages, p + 1))
                }
              >
                Next
                <ChevronRight className="size-3.5" />
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
