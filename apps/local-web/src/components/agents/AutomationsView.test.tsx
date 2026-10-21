import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AutomationsView } from './AutomationsView'
import { SshView } from './SshView'

function createMockClient() {
  return {
    listAutomations: vi.fn().mockResolvedValue([
      {
        id: 'auto-1',
        name: 'Watch Slurm Queue',
        prompt: 'Check squeue',
        command: 'squeue -u $USER',
        scheduleExpr: 'every 15m',
        scheduleKind: 'interval',
        scheduleLabel: 'Every 15m',
        sessionMode: 'continue',
        skillNames: ['tao-run-on-slurm', 'ssh', 'automate'],
        toolNames: [],
        mcpServerIds: [],
        continuity: true,
        contextFrom: [],
        wakeOnChangeOnly: true,
        runCount: 2,
        enabled: true,
        lastStatus: 'succeeded',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    ]),
    listAutomationTemplates: vi.fn().mockResolvedValue([
      {
        id: 'watch-slurm-queue',
        name: 'Watch Slurm Queue & Parse Job Logs',
        category: 'hpc_slurm',
        description: 'Poll squeue and sacct every 15 minutes.',
        scheduleExpr: 'every 15m',
        scheduleLabel: 'Every 15m',
        sessionMode: 'continue',
        prompt: 'Check squeue',
        command: 'squeue -u $USER',
        continuity: true,
        wakeOnChangeOnly: true,
        recommendedSpecialistSlug: 'ambitious-generalist',
        skillNames: ['tao-run-on-slurm', 'ssh', 'automate'],
        toolNames: ['ssh.exec'],
        badge: 'Scheduled · SSH / Slurm'
      }
    ]),
    listAutomationRuns: vi.fn().mockResolvedValue([
      {
        id: 'run-1',
        automationId: 'auto-1',
        automationName: 'Watch Slurm Queue',
        sessionId: 'sess-1',
        status: 'succeeded',
        triggerSource: 'schedule',
        startedAt: new Date().toISOString(),
        durationSeconds: 1.4,
        outputExcerpt: 'All jobs completed',
        wasCatchup: false
      }
    ]),
    listSshHosts: vi.fn().mockResolvedValue([
      {
        id: 'ssh-1',
        alias: 'hpc-cluster',
        host: 'login.hpc.edu',
        user: 'julio',
        port: 22,
        remotePort: 8787,
        defaultWorkdir: '/scratch/julio',
        source: 'saved',
        status: 'online',
        platform: 'Linux',
        arch: 'x86_64',
        slurmAvailable: true,
        sandwalkInstalled: true,
        sandwalkVersion: '0.1.13',
        daemonRunning: true,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    ]),
    listMcpServers: vi.fn().mockResolvedValue([
      {
        id: 'mcp-1',
        name: 'omnigraph',
        transport: 'stdio',
        enabled: true
      }
    ]),
    createAutomation: vi.fn().mockResolvedValue({
      id: 'auto-2',
      name: 'Watch Slurm Queue & Parse Job Logs',
      prompt: 'Check squeue',
      scheduleExpr: 'every 15m',
      scheduleKind: 'interval',
      scheduleLabel: 'Every 15m',
      sessionMode: 'continue',
      skillNames: ['tao-run-on-slurm', 'ssh'],
      toolNames: [],
      mcpServerIds: [],
      continuity: true,
      contextFrom: [],
      wakeOnChangeOnly: true,
      runCount: 0,
      enabled: true,
      lastStatus: 'idle',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }),
    updateAutomation: vi.fn().mockResolvedValue({
      id: 'auto-1',
      name: 'Updated Slurm Queue'
    }),
    deleteAutomation: vi.fn().mockResolvedValue(undefined),
    triggerAutomation: vi.fn().mockResolvedValue({
      id: 'run-2',
      status: 'succeeded'
    }),
    createSshHost: vi.fn().mockResolvedValue({
      id: 'ssh-2',
      alias: 'new-cluster',
      host: 'new.hpc.edu',
      port: 22
    }),
    deleteSshHost: vi.fn().mockResolvedValue(undefined),
    probeSshHost: vi.fn().mockResolvedValue({
      hostId: 'ssh-1',
      reachable: true,
      hostname: 'login-01',
      platform: 'Linux',
      slurmAvailable: true
    }),
    connectAndBootstrapSsh: vi.fn().mockResolvedValue({
      host: { id: 'ssh-1', alias: 'hpc-cluster', host: 'login.hpc.edu', port: 22 },
      steps: [{ step: 'probe', status: 'completed', detail: 'OK' }],
      localUrl: 'http://127.0.0.1:54111',
      watchdogInstalled: true
    }),
    execSshCommand: vi.fn().mockResolvedValue({
      hostId: 'ssh-1',
      command: 'uptime',
      exitCode: 0,
      stdout: 'up 42 days',
      stderr: '',
      durationSeconds: 0.2
    }),
    getSshSlurmStatus: vi.fn().mockResolvedValue({
      hostId: 'ssh-1',
      slurmAvailable: true,
      jobs: [
        {
          jobId: '991',
          partition: 'gpu',
          name: 'boltz-md',
          user: 'julio',
          state: 'RUNNING',
          timeUsed: '00:15:00',
          nodes: '1',
          reasonOrNodelist: 'gpu-01'
        }
      ],
      rawOutput: ''
    })
  }
}

describe('AutomationsView & SshView', () => {
  it('renders simplified Automations Hub, opens Editor from template, saves, and views Run History', async () => {
    const client = createMockClient()
    render(
      <MemoryRouter>
        <AutomationsView
          client={client as never}
          projects={[]}
          specialists={[
            {
              id: 'spec-1',
              name: 'Atlas',
              slug: 'ambitious-generalist',
              description: 'Generalist',
              instructions: '',
              color: 'blue',
              icon: 'wolf',
              skillNames: [],
              toolNames: [],
              mcpServerIds: [],
              mcpCatalogIds: [],
              enabled: true,
              createdAt: '',
              updatedAt: ''
            }
          ]}
        />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Watch Slurm Queue')).toBeTruthy()
    })

    // Click 'Use' on template to open streamlined Editor
    fireEvent.click(screen.getByRole('button', { name: 'Use' }))
    await waitFor(() => {
      expect(screen.getByText('Triggers')).toBeTruthy()
      expect(screen.getByText('New Session')).toBeTruthy()
      expect(screen.getByText('Same Thread')).toBeTruthy()
    })

    // Save new automation
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => {
      expect(client.createAutomation).toHaveBeenCalled()
    })

    // Return to Automations Hub
    fireEvent.click(screen.getByRole('button', { name: /Automations/i }))

    // Switch to Run History view
    fireEvent.click(screen.getByRole('button', { name: /Run History/i }))
    await waitFor(() => {
      expect(screen.getByText('All jobs completed')).toBeTruthy()
    })
  })

  it('renders simplified SshView, probes host, and opens Remote Command disclosure', async () => {
    const client = createMockClient()
    render(
      <MemoryRouter>
        <SshView client={client as never} />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('SSH')).toBeTruthy()
      expect(screen.getByText('Probe Host')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Probe Host' }))
    await waitFor(() => {
      expect(client.probeSshHost).toHaveBeenCalled()
    })

    // Open collapsible Run Remote Command section
    fireEvent.click(screen.getByRole('button', { name: /Run Remote Command/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Run via SSH' }))
    await waitFor(() => {
      expect(screen.getByText('up 42 days')).toBeTruthy()
    })
  })
})
