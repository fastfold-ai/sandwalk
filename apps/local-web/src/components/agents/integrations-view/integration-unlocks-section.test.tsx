import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSkill,
  IntegrationUnlock,
  ToolSummary
} from '@sandwalk/agent-ui-core'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { IntegrationUnlocksSection } from './integration-unlocks-section'

afterEach(() => {
  cleanup()
})

const fold: AgentSkill = {
  name: 'fold',
  description: 'Protein folding',
  tags: [],
  source: 'fastfold-ai/skills@skills/fold',
  author: 'FastFold',
  version: '1.0.0',
  updatedAt: null,
  iconSrc: null,
  enabled: true
}

const retrosynthesis: ToolSummary = {
  id: 'chemistry.retrosynthesis',
  name: 'Retrosynthesis',
  category: 'chemistry',
  status: 'stable',
  tier: 'core',
  description: 'Plan retrosynthetic routes.',
  requiresData: [],
  enabled: true,
  toggleable: false
}

const unlocks: IntegrationUnlock[] = [
  {
    kind: 'skill',
    id: 'fold',
    label: 'Protein folding',
    description: 'Submit FastFold structure predictions.',
    source: 'fastfold-ai/skills@skills/fold',
    requirement: 'install',
    installable: false,
    installed: null,
    statusDetail: null
  },
  {
    kind: 'tool',
    id: 'chemistry.retrosynthesis',
    label: 'IBM RXN retrosynthesis',
    description: 'Use IBM RXN before the heuristic fallback.',
    source: null,
    requirement: 'built_in',
    installable: false,
    installed: null,
    statusDetail: null
  }
]

function client() {
  const listSkills = vi
    .fn()
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([fold])
  const installSkill = vi.fn().mockResolvedValue(['fold'])
  const setSkillEnabled = vi.fn().mockResolvedValue({ ...fold, enabled: true })
  return {
    value: {
      listSkills,
      installSkill,
      setSkillEnabled,
      listTools: vi.fn().mockResolvedValue({
        data: [retrosynthesis],
        count: 1,
        categories: ['chemistry'],
        loadErrors: {}
      }),
      listDatasets: vi.fn().mockResolvedValue([]),
      updateToolEnabled: vi.fn(),
      installIntegrationCapability: vi.fn()
    } as unknown as LocalAgentClient,
    listSkills,
    installSkill,
    setSkillEnabled
  }
}

describe('IntegrationUnlocksSection', () => {
  it('renders live tool rows and installs missing referenced skills', async () => {
    const api = client()
    render(
      <MemoryRouter>
        <IntegrationUnlocksSection
          client={api.value}
          integrationKey="ibm-rxn"
          unlocks={unlocks}
        />
      </MemoryRouter>
    )

    expect(await screen.findByText('chemistry.retrosynthesis')).toBeTruthy()
    expect(screen.getByText('Not installed')).toBeTruthy()
    expect(document.querySelector('img')?.getAttribute('src')).toBe(
      '/ff_simbol_color.svg'
    )

    fireEvent.click(screen.getByRole('button', { name: 'Install' }))

    await waitFor(() => {
      expect(api.installSkill).toHaveBeenCalledWith(
        'fastfold-ai/skills@skills/fold'
      )
      expect(api.setSkillEnabled).toHaveBeenCalledWith('fold', true)
      expect(screen.getByText('Installed · Enabled')).toBeTruthy()
    })
    expect(api.listSkills).toHaveBeenCalledTimes(2)
  })

  it('shows Enable for installed disabled skills', async () => {
    const api = client()
    api.listSkills.mockReset()
    api.listSkills.mockResolvedValue([{ ...fold, enabled: false }])
    api.setSkillEnabled.mockResolvedValue({ ...fold, enabled: true })

    render(
      <MemoryRouter>
        <IntegrationUnlocksSection
          client={api.value}
          integrationKey="fastfold-cloud"
          unlocks={[unlocks[0]]}
        />
      </MemoryRouter>
    )

    expect(await screen.findByText('Installed · Disabled')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Enable' }))

    await waitFor(() => {
      expect(api.setSkillEnabled).toHaveBeenCalledWith('fold', true)
      expect(screen.getByText('Installed · Enabled')).toBeTruthy()
    })
    expect(screen.queryByRole('button', { name: 'Enable' })).toBeNull()
  })

  it('shows an explicit not-wired capability notice', () => {
    const api = client()
    render(
      <MemoryRouter>
        <IntegrationUnlocksSection
          client={api.value}
          integrationKey="langsmith"
          unlocks={[
            {
              kind: 'notice',
              id: 'langsmith-not-wired',
              label: 'No direct Sandwalk integration',
              description: 'No Sandwalk tool currently enables tracing.',
              source: null,
              requirement: 'not_wired',
              installable: false,
              installed: null,
              statusDetail: null
            }
          ]}
        />
      </MemoryRouter>
    )

    expect(screen.getByText('No direct Sandwalk integration')).toBeTruthy()
    expect(screen.getByText('Not wired')).toBeTruthy()
  })

  it('installs a missing integration capability and confirms its status', async () => {
    const api = client()
    const capability: IntegrationUnlock = {
      kind: 'capability',
      id: 'boltz-api-cli',
      label: 'boltz-api CLI',
      description: 'Required by the Boltz skill.',
      source: null,
      requirement: 'install',
      installable: true,
      installed: false,
      statusDetail: null
    }
    api.value.installIntegrationCapability = vi.fn().mockResolvedValue({
      unlocks: [
        { ...capability, installed: true, statusDetail: '/bin/boltz-api' }
      ]
    })
    render(
      <MemoryRouter>
        <IntegrationUnlocksSection
          client={api.value}
          integrationKey="boltz"
          unlocks={[capability]}
        />
      </MemoryRouter>
    )

    expect(screen.getByText('Not installed')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Install' }))

    await waitFor(() => expect(screen.getByText('Installed')).toBeTruthy())
    expect(api.value.installIntegrationCapability).toHaveBeenCalledWith(
      'boltz',
      'boltz-api-cli'
    )
  })
})
