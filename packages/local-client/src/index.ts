import type {
  AccountSummary,
  AgentClient,
  AgentEvent,
  AgentMessage,
  AgentModel,
  AgentProject,
  AgentSession,
  Specialist,
  AgentCatalogSkill,
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkill,
  AgentSkillBatchAction,
  AgentSkillBatchResult,
  AgentSkillDetail,
  AgentSkillSource,
  BackendHealth,
  CreateAgentModelInput,
  DatasetSummary,
  DatasetInstallResult,
  DoctorReport,
  EnvironmentPackageMutationResult,
  EnvironmentReport,
  FileProvider,
  FileWriteResult,
  IntegrationProvider,
  IntegrationSummary,
  IntegrationSetupResult,
  McpProvider,
  McpServer,
  McpCatalogEntry,
  ConnectMcpResult,
  ValidateMcpResult,
  McpToolDetail,
  ModelProfile,
  ModelProfileProbeResult,
  DiscoverModelEndpointInput,
  OnboardingSettings,
  ServerCacheInfo,
  ServerLifecycleResult,
  ServerStatusReport,
  StorageReport,
  ModelsProvider,
  RuntimeSettings,
  SandboxProbeReport,
  SandboxSettings,
  SessionSandboxStatus,
  SettingsProvider,
  SkillProvider,
  ToolBatchAction,
  ToolBatchResult,
  ToolCatalog,
  ToolSummary,
  UpsertModelProfileInput,
  PromptBudgetResponse,
  WorkspaceFile,
  WorkspaceFileContent,
  PtySessionInfo,
} from '@sandwalk/agent-ui-core'

export type LocalAgentClientOptions = {
  baseUrl: string
  apiKey?: string
}

export class LocalAgentClient
  implements
    AgentClient,
    FileProvider,
    SkillProvider,
    IntegrationProvider,
    SettingsProvider,
    ModelsProvider,
    McpProvider
{
  readonly baseUrl: string
  readonly apiKey?: string

  constructor(options: LocalAgentClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, '')
    this.apiKey = options.apiKey
  }

  private headers(extra?: HeadersInit): Headers {
    const headers = new Headers(extra)
    headers.set('accept', 'application/json')
    if (this.apiKey) headers.set('authorization', `Bearer ${this.apiKey}`)
    return headers
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}/v1${path}`
    const response = await fetch(url, {
      ...init,
      credentials: 'include',
      headers: this.headers(init.headers),
    })
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(
        `FastFold Agent API ${response.status}: ${detail || response.statusText} [${init.method || 'GET'} ${url}]`,
      )
    }
    if (response.status === 204) {
      return undefined as T
    }
    const text = await response.text()
    if (!text) return undefined as T
    return JSON.parse(text) as T
  }

  private normalizeValidateMcp(raw: Record<string, unknown>): ValidateMcpResult {
    const toolsRaw = raw.tools
    const tools = Array.isArray(toolsRaw)
      ? toolsRaw.map(item => String(item))
      : []
    const detailsRaw = raw.toolDetails ?? raw.tool_details
    const toolDetails: McpToolDetail[] = []
    if (Array.isArray(detailsRaw)) {
      for (const item of detailsRaw) {
        if (!item || typeof item !== 'object' || Array.isArray(item)) continue
        const row = item as Record<string, unknown>
        const name = String(row.name || '').trim()
        if (!name) continue
        const schema = row.inputSchema ?? row.input_schema
        toolDetails.push({
          name,
          title:
            typeof row.title === 'string' && row.title.trim()
              ? row.title.trim()
              : null,
          description:
            typeof row.description === 'string' && row.description.trim()
              ? row.description.trim()
              : null,
          inputSchema:
            schema && typeof schema === 'object' && !Array.isArray(schema)
              ? (schema as Record<string, unknown>)
              : null,
        })
      }
    }
    return {
      ok: Boolean(raw.ok),
      toolCount: Number(raw.toolCount ?? raw.tool_count ?? tools.length) || 0,
      message: String(raw.message || ''),
      tools,
      toolDetails,
    }
  }

  authStatus(signal?: AbortSignal): Promise<{
    authEnabled: boolean
    apiKeyConfigured: boolean
    authenticated?: boolean
  }> {
    return this.request('/auth/status', { signal })
  }

  async login(
    apiKey: string,
    options?: { remember?: boolean; signal?: AbortSignal },
  ): Promise<{ ok: boolean; authEnabled?: boolean }> {
    return this.request('/auth/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        apiKey,
        remember: Boolean(options?.remember),
      }),
      signal: options?.signal,
    })
  }

  logout(signal?: AbortSignal): Promise<{ ok: boolean }> {
    return this.request('/auth/logout', { method: 'POST', signal })
  }

  health(signal?: AbortSignal): Promise<BackendHealth> {
    return this.request<BackendHealth>('/health', { signal })
  }

  getServerStatus(signal?: AbortSignal): Promise<ServerStatusReport> {
    return this.request<ServerStatusReport>('/status', { signal })
  }

  stopServer(signal?: AbortSignal): Promise<ServerLifecycleResult> {
    return this.request<ServerLifecycleResult>('/server/stop', {
      method: 'POST',
      signal,
    })
  }

  restartServer(signal?: AbortSignal): Promise<ServerLifecycleResult> {
    return this.request<ServerLifecycleResult>('/server/restart', {
      method: 'POST',
      signal,
    })
  }

  clearRuntimeCache(signal?: AbortSignal): Promise<ServerCacheInfo> {
    return this.request<ServerCacheInfo>('/storage/cache/clear', {
      method: 'POST',
      signal,
    })
  }

  runDoctor(
    signalOrOptions?: AbortSignal | { scope?: 'full' | 'core'; signal?: AbortSignal },
    maybeSignal?: AbortSignal,
  ): Promise<DoctorReport> {
    let scope: 'full' | 'core' = 'full'
    let signal: AbortSignal | undefined
    if (
      signalOrOptions &&
      typeof signalOrOptions === 'object' &&
      !('aborted' in signalOrOptions)
    ) {
      scope = signalOrOptions.scope === 'core' ? 'core' : 'full'
      signal = signalOrOptions.signal ?? maybeSignal
    } else {
      signal = (signalOrOptions as AbortSignal | undefined) ?? maybeSignal
    }
    const query = scope === 'core' ? '?scope=core' : ''
    return this.request<DoctorReport>(`/doctor${query}`, { signal })
  }

  getStorage(signal?: AbortSignal): Promise<StorageReport> {
    return this.request<StorageReport>('/storage', { signal })
  }

  getEnvironment(signal?: AbortSignal): Promise<EnvironmentReport> {
    return this.request<EnvironmentReport>('/environment', { signal })
  }

  installEnvironmentPackage(
    name: string,
    options?: { allowUnlisted?: boolean; signal?: AbortSignal },
  ): Promise<EnvironmentPackageMutationResult> {
    return this.request<EnvironmentPackageMutationResult>(
      '/environment/packages/install',
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          name,
          allowUnlisted: Boolean(options?.allowUnlisted),
        }),
        signal: options?.signal,
      },
    )
  }

  uninstallEnvironmentPackage(
    name: string,
    signal?: AbortSignal,
  ): Promise<EnvironmentPackageMutationResult> {
    return this.request<EnvironmentPackageMutationResult>(
      '/environment/packages/uninstall',
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name }),
        signal,
      },
    )
  }

  async downloadDiagnostics(
    uiDiagnostics?: Record<string, unknown> | null,
    signal?: AbortSignal,
  ): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(`${this.baseUrl}/v1/doctor/diagnostics`, {
      method: 'POST',
      credentials: 'include',
      headers: this.headers({ 'content-type': 'application/json' }),
      body: JSON.stringify({ uiDiagnostics: uiDiagnostics ?? null }),
      signal,
    })
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(
        `FastFold Agent API ${response.status}: ${detail || response.statusText}`,
      )
    }
    const disposition = response.headers.get('content-disposition') || ''
    const match = disposition.match(/filename="?([^"]+)"?/i)
    const filename =
      match?.[1] ||
      `fastfold-diagnostics-${new Date().toISOString().replace(/[:.]/g, '')}.zip`
    return { blob: await response.blob(), filename }
  }

  async listSessions(
    options?: { projectId?: string | null; signal?: AbortSignal },
  ): Promise<AgentSession[]> {
    const params = new URLSearchParams()
    if (options?.projectId) params.set('projectId', options.projectId)
    const query = params.toString()
    const result = await this.request<{ data: AgentSession[] }>(
      `/sessions${query ? `?${query}` : ''}`,
      { signal: options?.signal },
    )
    return result.data
  }

  async listProjects(signal?: AbortSignal): Promise<AgentProject[]> {
    const result = await this.request<{ data: AgentProject[] }>('/projects', { signal })
    return result.data
  }

  getProject(projectId: string, signal?: AbortSignal): Promise<AgentProject> {
    return this.request<AgentProject>(`/projects/${encodeURIComponent(projectId)}`, {
      signal,
    })
  }

  createProject(
    input: {
      name: string
      description?: string | null
      agentContext?: string | null
      pinned?: boolean
    },
    signal?: AbortSignal,
  ): Promise<AgentProject> {
    return this.request<AgentProject>('/projects', {
      method: 'POST',
      body: JSON.stringify({
        name: input.name,
        description: input.description,
        agent_context: input.agentContext,
        pinned: Boolean(input.pinned),
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  updateProject(
    projectId: string,
    input: {
      name?: string
      description?: string | null
      agentContext?: string | null
      pinned?: boolean
    },
    signal?: AbortSignal,
  ): Promise<AgentProject> {
    return this.request<AgentProject>(`/projects/${encodeURIComponent(projectId)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        name: input.name,
        description: input.description,
        clear_description: input.description === null,
        agent_context: input.agentContext,
        clear_agent_context: input.agentContext === null,
        pinned: input.pinned,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  async deleteProject(projectId: string, signal?: AbortSignal): Promise<void> {
    await this.request<{ deleted: boolean }>(
      `/projects/${encodeURIComponent(projectId)}`,
      { method: 'DELETE', signal },
    )
  }

  async listSpecialists(signal?: AbortSignal): Promise<Specialist[]> {
    const result = await this.request<{ data: Specialist[] }>('/specialists', { signal })
    return result.data
  }

  getSpecialist(specialistId: string, signal?: AbortSignal): Promise<Specialist> {
    return this.request<Specialist>(`/specialists/${encodeURIComponent(specialistId)}`, {
      signal,
    })
  }

  createSpecialist(
    input: {
      name: string
      slug?: string | null
      description?: string | null
      instructions?: string | null
      color?: string
      icon?: string
      skillNames?: string[]
      toolNames?: string[]
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    },
    signal?: AbortSignal,
  ): Promise<Specialist> {
    return this.request<Specialist>('/specialists', {
      method: 'POST',
      body: JSON.stringify({
        name: input.name,
        slug: input.slug,
        description: input.description,
        instructions: input.instructions,
        color: input.color,
        icon: input.icon,
        skill_names: input.skillNames ?? [],
        tool_names: input.toolNames ?? [],
        mcp_server_ids: input.mcpServerIds ?? [],
        mcp_catalog_ids: input.mcpCatalogIds ?? [],
        enabled: input.enabled ?? true,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  updateSpecialist(
    specialistId: string,
    input: {
      name?: string
      slug?: string | null
      description?: string | null
      instructions?: string | null
      color?: string
      icon?: string
      skillNames?: string[]
      toolNames?: string[]
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    },
    signal?: AbortSignal,
  ): Promise<Specialist> {
    return this.request<Specialist>(`/specialists/${encodeURIComponent(specialistId)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        name: input.name,
        slug: input.slug,
        description: input.description,
        clear_description: input.description === null,
        instructions: input.instructions,
        clear_instructions: input.instructions === null,
        color: input.color,
        icon: input.icon,
        skill_names: input.skillNames,
        tool_names: input.toolNames,
        mcp_server_ids: input.mcpServerIds,
        mcp_catalog_ids: input.mcpCatalogIds,
        enabled: input.enabled,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  getPromptBudget(
    options?: {
      specialistId?: string | null
      projectId?: string | null
      sampleQuery?: string | null
    },
    signal?: AbortSignal,
  ): Promise<PromptBudgetResponse> {
    const params = new URLSearchParams()
    if (options?.specialistId) params.set('specialistId', options.specialistId)
    if (options?.projectId) params.set('projectId', options.projectId)
    if (options?.sampleQuery != null && options.sampleQuery !== '') {
      params.set('sampleQuery', options.sampleQuery)
    }
    const query = params.toString()
    return this.request<PromptBudgetResponse>(
      `/settings/prompt-budget${query ? `?${query}` : ''}`,
      { signal },
    )
  }

  async deleteSpecialist(specialistId: string, signal?: AbortSignal): Promise<void> {
    await this.request<{ deleted: boolean }>(
      `/specialists/${encodeURIComponent(specialistId)}`,
      { method: 'DELETE', signal },
    )
  }

  async searchSessions(query: string, signal?: AbortSignal): Promise<AgentSession[]> {
    const params = new URLSearchParams({ q: query })
    const result = await this.request<{ data: AgentSession[] }>(`/sessions/search?${params}`, {
      signal,
    })
    return result.data
  }

  createSession(
    input: {
      title?: string
      workspacePath?: string | null
      projectId?: string | null
      specialistId?: string | null
      sandboxBackend?: 'builtin' | 'modal' | null
    },
    signal?: AbortSignal,
  ): Promise<AgentSession> {
    return this.request<AgentSession>('/sessions', {
      method: 'POST',
      body: JSON.stringify({
        title: input.title,
        workspace_path: input.workspacePath,
        project_id: input.projectId,
        specialist_id: input.specialistId,
        sandbox_backend: input.sandboxBackend,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  updateSession(
    sessionId: string,
    input: {
      title?: string
      organizeLabel?: 'pinned' | 'archive' | null
      projectId?: string | null
      specialistId?: string | null
      sandboxBackend?: 'builtin' | 'modal' | null
    },
    signal?: AbortSignal,
  ): Promise<AgentSession> {
    return this.request<AgentSession>(`/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        title: input.title,
        organize_label: input.organizeLabel ?? undefined,
        clear_organize_label: input.organizeLabel === null,
        project_id: input.projectId ?? undefined,
        clear_project_id: input.projectId === null,
        specialist_id: input.specialistId ?? undefined,
        clear_specialist_id: input.specialistId === null,
        sandbox_backend: input.sandboxBackend ?? undefined,
        clear_sandbox_backend: input.sandboxBackend === null,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  getSessionSandbox(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionSandboxStatus> {
    return this.request<SessionSandboxStatus>(
      `/sessions/${encodeURIComponent(sessionId)}/sandbox`,
      { signal },
    )
  }

  sandboxStreamUrl(sessionId: string): string {
    const base = this.baseUrl.replace(/^http/, 'ws')
    const url = new URL(
      `${base}/v1/sessions/${encodeURIComponent(sessionId)}/sandbox/stream`,
    )
    if (this.apiKey) url.searchParams.set('token', this.apiKey)
    return url.toString()
  }

  startSessionSandbox(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionSandboxStatus> {
    return this.request<SessionSandboxStatus>(
      `/sessions/${encodeURIComponent(sessionId)}/sandbox/start`,
      { method: 'POST', signal },
    )
  }

  stopSessionSandbox(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionSandboxStatus> {
    return this.request<SessionSandboxStatus>(
      `/sessions/${encodeURIComponent(sessionId)}/sandbox/stop`,
      { method: 'POST', signal },
    )
  }

  restartSessionSandbox(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionSandboxStatus> {
    return this.request<SessionSandboxStatus>(
      `/sessions/${encodeURIComponent(sessionId)}/sandbox/restart`,
      { method: 'POST', signal },
    )
  }

  autoTitleSession(
    sessionId: string,
    input: { force?: boolean } = {},
    signal?: AbortSignal,
  ): Promise<AgentSession> {
    return this.request<AgentSession>(
      `/sessions/${encodeURIComponent(sessionId)}/title/auto`,
      {
        method: 'POST',
        body: JSON.stringify({ force: Boolean(input.force) }),
        headers: { 'content-type': 'application/json' },
        signal,
      },
    )
  }

  async deleteSession(sessionId: string, signal?: AbortSignal): Promise<void> {
    await this.request<{ deleted: boolean }>(`/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
      signal,
    })
  }

  async listMessages(sessionId: string, signal?: AbortSignal): Promise<AgentMessage[]> {
    const result = await this.request<{
      data: AgentMessage[]
      feedback?: Record<string, 'up' | 'down'>
    }>(`/sessions/${encodeURIComponent(sessionId)}/messages`, { signal })
    return result.data
  }

  async listEventHistory(sessionId: string, signal?: AbortSignal): Promise<AgentEvent[]> {
    const result = await this.request<{ data: AgentEvent[] }>(
      `/sessions/${encodeURIComponent(sessionId)}/events/history`,
      { signal },
    )
    return result.data
  }

  async getMessageFeedback(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<Record<string, 'up' | 'down'>> {
    const result = await this.request<{
      data: AgentMessage[]
      feedback?: Record<string, 'up' | 'down'>
    }>(`/sessions/${encodeURIComponent(sessionId)}/messages`, { signal })
    return result.feedback || {}
  }

  async setMessageFeedback(
    sessionId: string,
    messageId: string,
    reaction: 'up' | 'down' | null,
    signal?: AbortSignal,
  ): Promise<void> {
    await this.request(
      `/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/feedback`,
      {
        method: 'POST',
        body: JSON.stringify({ reaction }),
        headers: { 'content-type': 'application/json' },
        signal,
      },
    )
  }

  sendMessage(sessionId: string, content: string, signal?: AbortSignal): Promise<{ runId: string }> {
    return this.request<{ runId: string }>(
      `/sessions/${encodeURIComponent(sessionId)}/messages`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
        headers: { 'content-type': 'application/json' },
        signal,
      },
    )
  }

  async interrupt(sessionId: string, signal?: AbortSignal): Promise<boolean> {
    const result = await this.request<{ interrupted: boolean }>(
      `/sessions/${encodeURIComponent(sessionId)}/interrupt`,
      { method: 'POST', signal },
    )
    return result.interrupted
  }

  async streamEvents(
    sessionId: string,
    options: {
      afterSequence?: number
      signal?: AbortSignal
      onEvent: (event: AgentEvent) => void
    },
  ): Promise<void> {
    const query = new URLSearchParams()
    if (options.afterSequence) query.set('after_sequence', String(options.afterSequence))
    const suffix = query.size ? `?${query}` : ''
    const response = await fetch(
      `${this.baseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/events${suffix}`,
      {
        credentials: 'include',
        headers: this.headers({ accept: 'text/event-stream' }),
        signal: options.signal,
      },
    )
    if (!response.ok || !response.body) {
      throw new Error(`FastFold Agent event stream failed with status ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''

      for (const frame of frames) {
        const data = frame
          .split('\n')
          .filter((line) => line.startsWith('data:'))
          .map((line) => line.slice(5).trim())
          .join('')
        if (data) options.onEvent(JSON.parse(data) as AgentEvent)
      }
    }
  }

  async listFiles(sessionId: string, signal?: AbortSignal): Promise<WorkspaceFile[]> {
    const result = await this.request<{ data: WorkspaceFile[] }>(
      `/sessions/${encodeURIComponent(sessionId)}/files`,
      { signal },
    )
    return result.data
  }

  readFile(
    sessionId: string,
    path: string,
    signal?: AbortSignal,
  ): Promise<WorkspaceFileContent> {
    const query = new URLSearchParams({ path })
    return this.request<WorkspaceFileContent>(
      `/sessions/${encodeURIComponent(sessionId)}/files/content?${query}`,
      { signal },
    )
  }

  async writeFile(
    sessionId: string,
    input: {
      path: string
      content: string
      encoding?: 'text' | 'base64'
      baseVersion?: string | null
    },
    signal?: AbortSignal,
  ): Promise<FileWriteResult> {
    const response = await fetch(
      `${this.baseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/files/content`,
      {
        method: 'PUT',
        credentials: 'include',
        body: JSON.stringify({
          path: input.path,
          content: input.content,
          encoding: input.encoding || 'text',
          base_version: input.baseVersion,
        }),
        headers: this.headers({ 'content-type': 'application/json' }),
        signal,
      },
    )
    if (response.status === 409) {
      const body = (await response.json()) as { current: WorkspaceFileContent }
      return { ok: false, conflict: true, current: body.current }
    }
    if (!response.ok) {
      throw new Error(`FastFold Agent API ${response.status}: ${await response.text()}`)
    }
    return { ok: true, content: (await response.json()) as WorkspaceFileContent }
  }

  async uploadFile(
    sessionId: string,
    file: File,
    relativeDirectory = 'uploads',
    signal?: AbortSignal,
  ): Promise<WorkspaceFileContent> {
    const form = new FormData()
    form.append('file', file)
    if (relativeDirectory) form.append('relative_dir', relativeDirectory)
    const response = await fetch(
      `${this.baseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/files/upload`,
      {
        method: 'POST',
        credentials: 'include',
        body: form,
        headers: this.headers(),
        signal,
      },
    )
    if (!response.ok) {
      throw new Error(`FastFold Agent API ${response.status}: ${await response.text()}`)
    }
    return (await response.json()) as WorkspaceFileContent
  }

  async createFolder(
    sessionId: string,
    path: string,
    signal?: AbortSignal,
  ): Promise<void> {
    await this.request(`/sessions/${encodeURIComponent(sessionId)}/files/folders`, {
      method: 'POST',
      body: JSON.stringify({ path }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  async moveFile(
    sessionId: string,
    sourcePath: string,
    targetPath: string,
    signal?: AbortSignal,
  ): Promise<void> {
    await this.request(`/sessions/${encodeURIComponent(sessionId)}/files/move`, {
      method: 'POST',
      body: JSON.stringify({ source_path: sourcePath, target_path: targetPath }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  async deleteFile(
    sessionId: string,
    path: string,
    recursive = false,
    signal?: AbortSignal,
  ): Promise<void> {
    const query = new URLSearchParams({ path, recursive: String(recursive) })
    await this.request(`/sessions/${encodeURIComponent(sessionId)}/files?${query}`, {
      method: 'DELETE',
      signal,
    })
  }

  downloadUrl(sessionId: string, path: string): string {
    const query = new URLSearchParams({ path })
    return `${this.baseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/files/download?${query}`
  }

  async listSkills(signal?: AbortSignal): Promise<AgentSkill[]> {
    const result = await this.request<{ data: AgentSkill[] }>('/skills', { signal })
    return result.data
  }

  async listSkillSources(signal?: AbortSignal): Promise<AgentSkillSource[]> {
    const result = await this.request<{ data: AgentSkillSource[] }>('/skills/sources', { signal })
    return result.data
  }

  async searchSkillCatalog(
    query: string,
    limit = 12,
    signal?: AbortSignal,
  ): Promise<AgentCatalogSkill[]> {
    const params = new URLSearchParams({
      q: query,
      limit: String(limit),
    })
    const result = await this.request<{ data: AgentCatalogSkill[] }>(
      `/skills/catalog/search?${params.toString()}`,
      { signal },
    )
    return result.data
  }

  getCatalogSkillDetail(
    source: string,
    skill: string,
    signal?: AbortSignal,
  ): Promise<AgentCatalogSkillDetail> {
    const params = new URLSearchParams({ source, skill })
    return this.request<AgentCatalogSkillDetail>(
      `/skills/catalog/detail?${params.toString()}`,
      { signal },
    )
  }

  getCatalogSkillAudit(
    source: string,
    skill: string,
    signal?: AbortSignal,
  ): Promise<AgentCatalogSkillAudit> {
    const params = new URLSearchParams({ source, skill })
    return this.request<AgentCatalogSkillAudit>(
      `/skills/catalog/audit?${params.toString()}`,
      { signal },
    )
  }

  bulkSkillAction(
    action: AgentSkillBatchAction,
    names: string[],
    signal?: AbortSignal,
  ): Promise<AgentSkillBatchResult> {
    return this.request<AgentSkillBatchResult>('/skills/batch', {
      method: 'POST',
      body: JSON.stringify({ action, names }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  getSkill(name: string, signal?: AbortSignal): Promise<AgentSkillDetail> {
    return this.request<AgentSkillDetail>(`/skills/${encodeURIComponent(name)}`, { signal })
  }

  setSkillEnabled(
    name: string,
    enabled: boolean,
    signal?: AbortSignal,
  ): Promise<AgentSkillDetail> {
    return this.request<AgentSkillDetail>(`/skills/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  async installSkill(source: string, signal?: AbortSignal): Promise<string[]> {
    const result = await this.request<{ installed: string[] }>('/skills', {
      method: 'POST',
      body: JSON.stringify({ source }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
    return result.installed
  }

  async installSkillFile(file: File, signal?: AbortSignal): Promise<string[]> {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`${this.baseUrl}/v1/skills/upload`, {
      method: 'POST',
      credentials: 'include',
      body: form,
      headers: this.headers(),
      signal,
    })
    if (!response.ok) {
      throw new Error(`FastFold Agent API ${response.status}: ${await response.text()}`)
    }
    const result = (await response.json()) as { installed: string[] }
    return result.installed
  }

  async removeSkill(name: string, signal?: AbortSignal): Promise<void> {
    await this.request(`/skills/${encodeURIComponent(name)}`, {
      method: 'DELETE',
      signal,
    })
  }

  async upgradeSkills(signal?: AbortSignal): Promise<string[]> {
    const result = await this.request<{ installed: string[] }>('/skills/upgrade', {
      method: 'POST',
      signal,
    })
    return result.installed
  }

  async listIntegrations(signal?: AbortSignal): Promise<IntegrationSummary[]> {
    const result = await this.request<{ data: IntegrationSummary[] }>('/integrations', { signal })
    // Legacy global OpenAI-compatible key is redundant with per–Local LLM profile keys.
    return result.data.filter(item => item.key !== 'openai-compatible')
  }

  updateIntegration(
    key: string,
    values: Record<string, string>,
    signal?: AbortSignal,
  ): Promise<IntegrationSummary> {
    return this.request<IntegrationSummary>(`/integrations/${encodeURIComponent(key)}`, {
      method: 'PUT',
      body: JSON.stringify({ values }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  removeIntegration(key: string, signal?: AbortSignal): Promise<IntegrationSummary> {
    return this.request<IntegrationSummary>(`/integrations/${encodeURIComponent(key)}`, {
      method: 'DELETE',
      signal,
    })
  }

  autofillIntegration(key: string, signal?: AbortSignal): Promise<IntegrationSummary> {
    return this.request<IntegrationSummary>(
      `/integrations/${encodeURIComponent(key)}/autofill`,
      {
        method: 'POST',
        signal,
      },
    )
  }

  setupIntegration(
    key: string,
    workingDirectory?: string | null,
    signal?: AbortSignal,
  ): Promise<IntegrationSetupResult> {
    const body =
      workingDirectory && workingDirectory.trim()
        ? JSON.stringify({ workingDirectory: workingDirectory.trim() })
        : undefined
    return this.request<IntegrationSetupResult>(
      `/integrations/${encodeURIComponent(key)}/setup`,
      {
        method: 'POST',
        body,
        headers: body ? { 'content-type': 'application/json' } : undefined,
        signal,
      },
    )
  }

  async validateIntegration(
    key: string,
    signal?: AbortSignal,
  ): Promise<{ ok: boolean; message: string }> {
    return this.request<{ ok: boolean; message: string }>(
      `/integrations/${encodeURIComponent(key)}/validate`,
      { method: 'POST', signal },
    )
  }

  getRuntimeSettings(signal?: AbortSignal): Promise<RuntimeSettings> {
    return this.request<RuntimeSettings>('/settings/runtime', { signal })
  }

  updateRuntimeSettings(
    changes: Partial<RuntimeSettings>,
    signal?: AbortSignal,
  ): Promise<RuntimeSettings> {
    return this.request<RuntimeSettings>('/settings/runtime', {
      method: 'PATCH',
      body: JSON.stringify({
        provider: changes.provider,
        model: changes.model,
        openai_base_url: changes.openaiBaseUrl,
        agent_profile: changes.agentProfile,
        tool_mode: changes.toolMode,
        reasoning_effort: changes.reasoningEffort,
        reasoning_fast: changes.reasoningFast,
        recursion_limit: changes.recursionLimit,
        max_sdk_turns: changes.maxSdkTurns,
        group_tool_traces: changes.groupToolTraces,
        tool_trace_detail_limit: changes.toolTraceDetailLimit,
        background_watch_timeout_s: changes.backgroundWatchTimeoutS,
        interrupt_drain_timeout_s: changes.interruptDrainTimeoutS,
        parallel_max_threads: changes.parallelMaxThreads,
        tool_health_enabled: changes.toolHealthEnabled,
        tool_health_fail_threshold: changes.toolHealthFailThreshold,
        tool_health_suppress_seconds: changes.toolHealthSuppressSeconds,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  getOnboardingSettings(signal?: AbortSignal): Promise<OnboardingSettings> {
    return this.request<OnboardingSettings>('/settings/onboarding', { signal })
  }

  updateOnboardingSettings(
    changes: Partial<OnboardingSettings>,
    signal?: AbortSignal,
  ): Promise<OnboardingSettings> {
    return this.request<OnboardingSettings>('/settings/onboarding', {
      method: 'PATCH',
      body: JSON.stringify({
        completed: changes.completed,
        step: changes.step,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  getSandboxSettings(signal?: AbortSignal): Promise<SandboxSettings> {
    return this.request<SandboxSettings>('/settings/sandbox', { signal })
  }

  updateSandboxSettings(
    changes: Partial<SandboxSettings>,
    signal?: AbortSignal,
  ): Promise<SandboxSettings> {
    return this.request<SandboxSettings>('/settings/sandbox', {
      method: 'PATCH',
      body: JSON.stringify({
        backend: changes.backend,
        modal_app: changes.modalApp,
        cpu_image: changes.cpuImage,
        gpu_image: changes.gpuImage,
        pip_packages: changes.pipPackages,
        compute_type: changes.computeType,
        gpu_class: changes.gpuClass,
        cpu_cores: changes.cpuCores,
        ram_gb: changes.ramGb,
        idle_ttl_seconds: changes.idleTtlSeconds,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  probeSandboxSettings(signal?: AbortSignal): Promise<SandboxProbeReport> {
    return this.request<SandboxProbeReport>('/settings/sandbox/probe', {
      method: 'POST',
      signal,
    })
  }

  getAccount(options?: {
    checkUpdates?: boolean
    signal?: AbortSignal
  }): Promise<AccountSummary> {
    const params = new URLSearchParams()
    if (options?.checkUpdates) params.set('check_updates', 'true')
    const query = params.toString()
    return this.request<AccountSummary>(`/account${query ? `?${query}` : ''}`, {
      signal: options?.signal,
    })
  }

  logoutAccount(signal?: AbortSignal): Promise<AccountSummary> {
    return this.request<AccountSummary>('/account/logout', {
      method: 'POST',
      signal,
    })
  }

  async listModels(options?: {
    enabledOnly?: boolean
    discover?: boolean
    signal?: AbortSignal
  }): Promise<AgentModel[]> {
    const params = new URLSearchParams()
    if (options?.enabledOnly) params.set('enabled_only', 'true')
    if (options?.discover === false) params.set('discover', 'false')
    const query = params.toString()
    const result = await this.request<{ data: AgentModel[] }>(
      `/models${query ? `?${query}` : ''}`,
      { signal: options?.signal },
    )
    return result.data
  }

  updateModelEnabled(
    modelId: string,
    enabled: boolean,
    signal?: AbortSignal,
  ): Promise<AgentModel> {
    return this.request<AgentModel>(`/models/${encodeURIComponent(modelId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  createCustomModel(
    input: CreateAgentModelInput,
    signal?: AbortSignal,
  ): Promise<AgentModel> {
    return this.request<AgentModel>('/models', {
      method: 'POST',
      body: JSON.stringify({
        id: input.id,
        provider: input.provider || 'openai',
        label: input.label,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  async deleteCustomModel(
    modelId: string,
    signal?: AbortSignal,
  ): Promise<void> {
    await this.request(`/models/${encodeURIComponent(modelId)}`, {
      method: 'DELETE',
      signal,
    })
  }

  async listModelProfiles(options?: {
    includeCloud?: boolean
    signal?: AbortSignal
  }): Promise<ModelProfile[]> {
    const params = new URLSearchParams()
    if (options?.includeCloud === false) params.set('include_cloud', 'false')
    const query = params.toString()
    const result = await this.request<{ data: ModelProfile[] }>(
      `/model-profiles${query ? `?${query}` : ''}`,
      { signal: options?.signal },
    )
    return result.data
  }

  createModelProfile(
    input: UpsertModelProfileInput,
    signal?: AbortSignal,
  ): Promise<ModelProfile> {
    return this.request<ModelProfile>('/model-profiles', {
      method: 'POST',
      body: JSON.stringify({
        id: input.id,
        label: input.label,
        backend: input.backend,
        base_url: input.baseUrl,
        api_key: input.apiKey,
        default_model: input.defaultModel,
        discovery: input.discovery,
        set_active: input.setActive,
        set_default: input.setDefault,
      }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  updateModelProfile(
    profileId: string,
    input: UpsertModelProfileInput,
    signal?: AbortSignal,
  ): Promise<ModelProfile> {
    return this.request<ModelProfile>(
      `/model-profiles/${encodeURIComponent(profileId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          id: profileId,
          label: input.label,
          backend: input.backend,
          base_url: input.baseUrl,
          api_key: input.apiKey,
          default_model: input.defaultModel,
          discovery: input.discovery,
          set_active: input.setActive,
          set_default: input.setDefault,
        }),
        headers: { 'content-type': 'application/json' },
        signal,
      },
    )
  }

  async deleteModelProfile(
    profileId: string,
    signal?: AbortSignal,
  ): Promise<void> {
    await this.request(`/model-profiles/${encodeURIComponent(profileId)}`, {
      method: 'DELETE',
      signal,
    })
  }

  probeModelProfile(
    profileId: string,
    signal?: AbortSignal,
  ): Promise<ModelProfileProbeResult> {
    return this.request<ModelProfileProbeResult>(
      `/model-profiles/${encodeURIComponent(profileId)}/probe`,
      { method: 'POST', signal },
    )
  }

  discoverModelEndpoint(
    input: DiscoverModelEndpointInput,
    signal?: AbortSignal,
  ): Promise<ModelProfileProbeResult> {
    return this.request<ModelProfileProbeResult>('/model-profiles/discover', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        backend: input.backend ?? undefined,
        baseUrl: input.baseUrl,
        apiKey: input.apiKey ?? undefined,
      }),
      signal,
    })
  }

  async listDatasets(signal?: AbortSignal): Promise<DatasetSummary[]> {
    const result = await this.request<{ data: DatasetSummary[] }>('/datasets', {
      signal,
    })
    return result.data
  }

  installDataset(
    datasetId: string,
    signal?: AbortSignal,
  ): Promise<DatasetInstallResult> {
    return this.request<DatasetInstallResult>(
      `/datasets/${encodeURIComponent(datasetId)}/install`,
      { method: 'POST', signal },
    )
  }

  removeDataset(
    datasetId: string,
    signal?: AbortSignal,
  ): Promise<DatasetInstallResult> {
    return this.request<DatasetInstallResult>(
      `/datasets/${encodeURIComponent(datasetId)}`,
      { method: 'DELETE', signal },
    )
  }

  async listTools(options?: {
    enabledOnly?: boolean
    signal?: AbortSignal
  }): Promise<ToolCatalog> {
    const params = new URLSearchParams()
    if (options?.enabledOnly) params.set('enabled_only', 'true')
    const query = params.toString()
    return this.request<ToolCatalog>(`/tools${query ? `?${query}` : ''}`, {
      signal: options?.signal,
    })
  }

  updateToolEnabled(
    toolId: string,
    enabled: boolean,
    signal?: AbortSignal,
  ): Promise<ToolSummary> {
    return this.request<ToolSummary>(`/tools/${encodeURIComponent(toolId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  batchUpdateTools(
    action: ToolBatchAction,
    ids: string[],
    signal?: AbortSignal,
  ): Promise<ToolBatchResult> {
    return this.request<ToolBatchResult>('/tools/batch', {
      method: 'POST',
      body: JSON.stringify({ action, ids }),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  async listMcpServers(signal?: AbortSignal): Promise<McpServer[]> {
    const result = await this.request<{ data: McpServer[] }>('/mcp-servers', { signal })
    return result.data
  }

  async listMcpCatalog(signal?: AbortSignal): Promise<McpCatalogEntry[]> {
    const result = await this.request<{ data: McpCatalogEntry[] }>(
      '/mcp-servers/catalog',
      { signal },
    )
    return result.data
  }

  connectMcpCatalog(
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string },
    signal?: AbortSignal,
  ): Promise<ConnectMcpResult> {
    return this.request<ConnectMcpResult>(
      `/mcp-servers/catalog/${encodeURIComponent(catalogId)}/connect`,
      {
        method: 'POST',
        body: JSON.stringify(input),
        headers: { 'content-type': 'application/json' },
        signal,
      },
    )
  }

  disconnectMcpCatalog(
    catalogId: string,
    signal?: AbortSignal,
  ): Promise<ConnectMcpResult> {
    return this.request<ConnectMcpResult>(
      `/mcp-servers/catalog/${encodeURIComponent(catalogId)}/connect`,
      {
        method: 'DELETE',
        signal,
      },
    )
  }

  setMcpCatalogEnabled(
    catalogId: string,
    enabled: boolean,
    signal?: AbortSignal,
  ): Promise<ConnectMcpResult> {
    return this.request<ConnectMcpResult>(
      `/mcp-servers/catalog/${encodeURIComponent(catalogId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
        headers: { 'content-type': 'application/json' },
        signal,
      },
    )
  }

  async validateMcpCatalog(
    catalogId: string,
    signal?: AbortSignal,
  ): Promise<ValidateMcpResult> {
    const raw = await this.request<Record<string, unknown>>(
      `/mcp-servers/catalog/${encodeURIComponent(catalogId)}/validate`,
      {
        method: 'POST',
        signal,
      },
    )
    return this.normalizeValidateMcp(raw || {})
  }

  async validateMcpServer(
    serverId: string,
    signal?: AbortSignal,
  ): Promise<ValidateMcpResult> {
    const raw = await this.request<Record<string, unknown>>(
      `/mcp-servers/${encodeURIComponent(serverId)}/validate`,
      {
        method: 'POST',
        signal,
      },
    )
    return this.normalizeValidateMcp(raw || {})
  }

  createMcpServer(
    input: Omit<McpServer, 'id' | 'createdAt' | 'updatedAt'>,
    signal?: AbortSignal,
  ): Promise<McpServer> {
    return this.request<McpServer>('/mcp-servers', {
      method: 'POST',
      body: JSON.stringify(input),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  updateMcpServer(
    id: string,
    changes: Partial<Omit<McpServer, 'id' | 'transport' | 'createdAt' | 'updatedAt'>>,
    signal?: AbortSignal,
  ): Promise<McpServer> {
    return this.request<McpServer>(`/mcp-servers/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
      headers: { 'content-type': 'application/json' },
      signal,
    })
  }

  async deleteMcpServer(id: string, signal?: AbortSignal): Promise<void> {
    await this.request(`/mcp-servers/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      signal,
    })
  }

  async listPtySessions(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<PtySessionInfo[]> {
    const result = await this.request<{ data: PtySessionInfo[] }>(
      `/sessions/${encodeURIComponent(sessionId)}/pty`,
      { signal },
    )
    return result.data
  }

  createPtySession(
    sessionId: string,
    input?: { title?: string; cols?: number; rows?: number },
    signal?: AbortSignal,
  ): Promise<PtySessionInfo> {
    return this.request<PtySessionInfo>(
      `/sessions/${encodeURIComponent(sessionId)}/pty`,
      {
        method: 'POST',
        body: JSON.stringify(input || {}),
        headers: { 'content-type': 'application/json' },
        signal,
      },
    )
  }

  updatePtySession(
    sessionId: string,
    ptyId: string,
    input: { title?: string; cols?: number; rows?: number },
    signal?: AbortSignal,
  ): Promise<PtySessionInfo> {
    return this.request<PtySessionInfo>(
      `/sessions/${encodeURIComponent(sessionId)}/pty/${encodeURIComponent(ptyId)}`,
      {
        method: 'PUT',
        body: JSON.stringify(input),
        headers: { 'content-type': 'application/json' },
        signal,
      },
    )
  }

  async deletePtySession(
    sessionId: string,
    ptyId: string,
    signal?: AbortSignal,
  ): Promise<void> {
    await this.request(
      `/sessions/${encodeURIComponent(sessionId)}/pty/${encodeURIComponent(ptyId)}`,
      { method: 'DELETE', signal },
    )
  }

  ptyConnectUrl(sessionId: string, ptyId: string): string {
    const base = this.baseUrl.replace(/^http/, 'ws')
    const url = new URL(
      `${base}/v1/sessions/${encodeURIComponent(sessionId)}/pty/${encodeURIComponent(ptyId)}/connect`,
    )
    if (this.apiKey) url.searchParams.set('token', this.apiKey)
    return url.toString()
  }
}
