import { describe, expect, it } from 'vitest'

import {
  agentStatusKey,
  DEFAULT_AGENT_STATUS,
  MODEL_SLOW_AFTER_MS,
  MODEL_SLOW_STATUS,
  resolveAgentStatus,
  statusLabelForTool,
  WAITING_ON_MODEL_AFTER_MS,
  WAITING_ON_MODEL_STATUS
} from './agent-status-words'

describe('agent-status-words', () => {
  it('defaults to planning next moves', () => {
    expect(resolveAgentStatus([])).toBe(DEFAULT_AGENT_STATUS)
    expect(resolveAgentStatus(null)).toBe(DEFAULT_AGENT_STATUS)
  })

  it('maps known tools to informative labels', () => {
    expect(statusLabelForTool('run_python')).toBe('Running Python')
    expect(statusLabelForTool('search_tools')).toBe('Searching tools')
    expect(statusLabelForTool('skills_manage')).toBe('Managing skills')
    expect(statusLabelForTool('read_file')).toBe('Reading file')
  })

  it('prefers the pending tool over completed ones', () => {
    expect(
      resolveAgentStatus([
        {
          name: 'search_tools',
          status: 'completed',
          startedAt: '2026-01-01T00:00:00Z'
        },
        {
          name: 'run_python',
          status: 'pending',
          startedAt: '2026-01-01T00:00:01Z'
        }
      ])
    ).toBe('Running Python')
  })

  it('returns planning when nothing is pending', () => {
    expect(
      resolveAgentStatus([
        {
          name: 'run_python',
          status: 'completed',
          startedAt: '2026-01-01T00:00:00Z'
        }
      ])
    ).toBe(DEFAULT_AGENT_STATUS)
  })

  it('escalates to waiting / slow when the model is quiet', () => {
    expect(
      resolveAgentStatus([], { quietMs: WAITING_ON_MODEL_AFTER_MS })
    ).toBe(WAITING_ON_MODEL_STATUS)
    expect(resolveAgentStatus([], { quietMs: MODEL_SLOW_AFTER_MS })).toBe(
      MODEL_SLOW_STATUS
    )
    expect(
      resolveAgentStatus(
        [
          {
            id: '1',
            name: 'run_python',
            status: 'pending',
            startedAt: 't1'
          }
        ],
        { quietMs: MODEL_SLOW_AFTER_MS }
      )
    ).toBe('Running Python')
  })

  it('changes status key when the pending tool changes', () => {
    const first = agentStatusKey([
      { id: '1', name: 'search_tools', status: 'pending', startedAt: 't1' }
    ])
    const second = agentStatusKey([
      { id: '1', name: 'search_tools', status: 'completed', startedAt: 't1' },
      { id: '2', name: 'run_python', status: 'pending', startedAt: 't2' }
    ])
    expect(first).not.toBe(second)
    expect(second).toContain('2')
    expect(second).toContain('pending')
    expect(
      agentStatusKey([
        { id: '1', name: 'search_tools', status: 'completed', startedAt: 't1' }
      ])
    ).toBe('planning')
    expect(
      agentStatusKey([], { quietMs: WAITING_ON_MODEL_AFTER_MS })
    ).toBe('waiting-on-model')
  })

  it('updates status as each new pending tool appears', () => {
    expect(
      resolveAgentStatus([
        {
          id: '1',
          name: 'search_tools',
          status: 'completed',
          startedAt: 't1'
        }
      ])
    ).toBe(DEFAULT_AGENT_STATUS)
    expect(
      resolveAgentStatus([
        {
          id: '1',
          name: 'search_tools',
          status: 'completed',
          startedAt: 't1'
        },
        {
          id: '2',
          name: 'run_python',
          status: 'pending',
          startedAt: 't2'
        }
      ])
    ).toBe('Running Python')
  })
})
