import type { E2EEnv } from './env'

export type SeededSession = { id: string; title: string | null }
export type SeededTerminal = { id: string; title: string | null }

/** Minimal REST client for seeding/cleanup — mirrors LocalAgentClient paths. */
export class E2EApi {
  constructor(private readonly env: E2EEnv) {}

  private headers(): Record<string, string> {
    const headers: Record<string, string> = { 'content-type': 'application/json' }
    if (this.env.apiKey) headers.Authorization = `Bearer ${this.env.apiKey}`
    return headers
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.env.apiUrl}/v1${path}`, {
      ...init,
      headers: { ...this.headers(), ...(init?.headers as Record<string, string> | undefined) }
    })
    if (!response.ok) {
      const text = await response.text().catch(() => '')
      throw new Error(`API ${response.status} ${init?.method ?? 'GET'} ${path}: ${text.slice(0, 200)}`)
    }
    if (response.status === 204) return undefined as T
    const text = await response.text()
    return (text ? JSON.parse(text) : undefined) as T
  }

  async health(): Promise<boolean> {
    try {
      const response = await fetch(`${this.env.apiUrl}/v1/health`, { headers: this.headers() })
      return response.ok
    } catch {
      return false
    }
  }

  createSession(
    title: string,
    options: { provider?: string | null; model?: string | null } = {}
  ): Promise<SeededSession> {
    return this.request<SeededSession>('/sessions', {
      method: 'POST',
      body: JSON.stringify({
        title,
        workspacePath: null,
        projectId: null,
        clientSurface: 'ui',
        ...(options.provider ? { provider: options.provider } : {}),
        ...(options.model ? { model: options.model } : {})
      })
    })
  }

  deleteSession(id: string): Promise<void> {
    return this.request<void>(`/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' })
  }

  createTerminal(title: string): Promise<SeededTerminal> {
    return this.request<SeededTerminal>('/terminals', {
      method: 'POST',
      body: JSON.stringify({ title, projectId: null, workspacePath: null })
    })
  }

  deleteTerminal(id: string): Promise<void> {
    return this.request<void>(`/terminals/${encodeURIComponent(id)}`, { method: 'DELETE' })
  }

  /** Send a chat message and return the request latency (ms) with the run id. */
  async sendMessage(sessionId: string, content: string): Promise<{ runId: string; latencyMs: number }> {
    const started = performance.now()
    const result = await this.request<{ runId: string }>(
      `/sessions/${encodeURIComponent(sessionId)}/messages`,
      { method: 'POST', body: JSON.stringify({ content }) }
    )
    return { runId: result.runId, latencyMs: Math.round(performance.now() - started) }
  }

  getSession(id: string): Promise<{ id: string; status: string }> {
    return this.request<{ id: string; status: string }>(`/sessions/${encodeURIComponent(id)}`)
  }

  async listMessages(id: string): Promise<Array<{ role: string; content?: unknown }>> {
    const result = await this.request<{ data: Array<{ role: string; content?: unknown }> }>(
      `/sessions/${encodeURIComponent(id)}/messages`
    )
    return result.data
  }

  /** Median round-trip of `GET /v1/health` over `samples` requests. */
  async healthLatencyMs(samples = 10): Promise<number> {
    const times: number[] = []
    for (let i = 0; i < samples; i += 1) {
      const started = performance.now()
      await fetch(`${this.env.apiUrl}/v1/health`, { headers: this.headers() })
      times.push(performance.now() - started)
    }
    times.sort((a, b) => a - b)
    return Math.round(times[Math.floor(times.length / 2)])
  }
}
