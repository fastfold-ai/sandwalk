import { LocalAgentClient } from '@sandwalk/agent-local-client'

export async function validateIntegrationOrProbeModal(
  client: LocalAgentClient,
  key: string
): Promise<{ ok: boolean; message: string }> {
  if (key === 'modal') {
    try {
      const report = await client.probeSandboxSettings()
      const failed = report.steps.find(step => !step.ok)
      return {
        ok: report.ok,
        message: report.ok
          ? 'Modal sandbox probe passed.'
          : failed?.detail || 'Modal sandbox probe failed.'
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      const missingProbe =
        /\/v1\/settings\/sandbox\/probe/i.test(message) &&
        /\b404\b|not found/i.test(message)
      return {
        ok: false,
        message: missingProbe
          ? 'Probe endpoint missing on this agent server. Restart sandwalk / `sandwalk serve` after updating the CLI, then retry.'
          : message
      }
    }
  }
  return client.validateIntegration(key)
}
