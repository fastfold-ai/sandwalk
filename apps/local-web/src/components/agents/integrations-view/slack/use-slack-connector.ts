import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  SlackAllowedUser,
  SlackConnectorStatus,
  SlackDirectory,
  SlackParkedMessage
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useState } from 'react'

export function useSlackConnector(client: LocalAgentClient) {
  const [status, setStatus] = useState<SlackConnectorStatus | null>(null)
  const [parked, setParked] = useState<SlackParkedMessage[]>([])
  const [people, setPeople] = useState<Record<string, SlackAllowedUser[]>>({})
  const [directories, setDirectories] = useState<
    Record<string, SlackDirectory>
  >({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setError(null)
    try {
      const next = await client.getSlackStatus()
      setStatus(next)
      const [queued, ...rosters] = await Promise.all([
        client.listSlackParked(),
        ...next.workspaces.map(workspace =>
          client
            .listSlackPeople(workspace.teamId)
            .then(result => [workspace.teamId, result.data] as const)
        )
      ])
      setParked(queued.data)
      setPeople(Object.fromEntries(rosters))

      // The directory hits Slack, so let it settle separately — a slow or
      // rate-limited users.list must not hold up the rest of the panel.
      void Promise.all(
        next.workspaces.map(workspace =>
          client
            .getSlackDirectory(workspace.teamId)
            .then(result => [workspace.teamId, result] as const)
            .catch(() => null)
        )
      ).then(results => {
        setDirectories(
          Object.fromEntries(
            results.filter((item): item is [string, SlackDirectory] =>
              Boolean(item)
            )
          )
        )
      })
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to load Slack status'
      )
    } finally {
      setLoading(false)
    }
  }, [client])

  useEffect(() => {
    void reload()
  }, [reload])

  /** Run a mutation, surface its error, and refresh. Returns success. */
  const act = useCallback(
    async (operation: () => Promise<unknown>) => {
      setBusy(true)
      setError(null)
      try {
        await operation()
        await reload()
        return true
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Slack request failed')
        return false
      } finally {
        setBusy(false)
      }
    },
    [reload]
  )

  /** Re-fetch people/channels for one workspace from Slack. */
  const refreshDirectory = useCallback(
    async (teamId: string) => {
      setBusy(true)
      setError(null)
      try {
        const result = await client.getSlackDirectory(teamId)
        setDirectories(current => ({ ...current, [teamId]: result }))
        return true
      } catch (cause) {
        setError(
          cause instanceof Error
            ? cause.message
            : 'Unable to refresh Slack channels'
        )
        return false
      } finally {
        setBusy(false)
      }
    },
    [client]
  )

  return {
    status,
    parked,
    people,
    directories,
    loading,
    busy,
    error,
    setError,
    reload,
    refreshDirectory,
    act
  }
}

export type SlackConnectorState = ReturnType<typeof useSlackConnector>
