import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useEffect, useRef } from 'react'

function fingerprint(
  sites: Awaited<ReturnType<LocalAgentClient['listSites']>>,
  sessionId: string
) {
  const latest = sites
    .filter(site => site.sourceSessionId === sessionId)
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))[0]
  return latest ? `${latest.id}:${latest.updatedAt}` : null
}

export function useSessionSiteAutoPreview({
  client,
  sessionId,
  workspaceVersion,
  onSiteReady
}: {
  client: LocalAgentClient
  sessionId: string | null
  workspaceVersion: number
  onSiteReady: () => void
}) {
  const known = useRef<string | null>(null)
  const version = useRef(workspaceVersion)
  const generation = useRef(0)

  useEffect(() => {
    generation.current += 1
    const current = generation.current
    version.current = workspaceVersion
    known.current = null
    if (!sessionId) return
    const controller = new AbortController()
    void client
      .listSites({ signal: controller.signal })
      .then(sites => {
        if (generation.current !== current) return
        known.current = fingerprint(sites, sessionId)
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [client, sessionId])

  useEffect(() => {
    if (!sessionId || version.current === workspaceVersion) return
    version.current = workspaceVersion
    generation.current += 1
    const current = generation.current
    const previous = known.current
    const controller = new AbortController()
    void client
      .listSites({ signal: controller.signal })
      .then(sites => {
        if (generation.current !== current) return
        const next = fingerprint(sites, sessionId)
        known.current = next
        if (next && next !== previous) onSiteReady()
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [client, onSiteReady, sessionId, workspaceVersion])
}
