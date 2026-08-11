import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HitlDecisionCard } from './HitlDecisionCard'

afterEach(() => {
  cleanup()
})

describe('HitlDecisionCard', () => {
  it('approves skill remove for the rest of the run', () => {
    const onSubmit = vi.fn()
    render(
      <HitlDecisionCard
        actionRequests={[
          {
            name: 'skills_manage',
            args: { action: 'remove', name: 'gws-drive' }
          }
        ]}
        reviewConfigs={[
          {
            actionName: 'skills_manage',
            allowedDecisions: ['approve', 'edit', 'reject']
          }
        ]}
        onSubmit={onSubmit}
      />
    )

    expect(screen.getByText('Remove skills')).toBeTruthy()
    expect(
      screen.getByText(/Approving allows all skill install\/remove/)
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Approve' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Approve once' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(onSubmit).toHaveBeenCalledWith([
      { type: 'approve', scope: 'remaining' }
    ])
  })

  it('labels Approve all (n) for non-skill stacked actions', () => {
    const onSubmit = vi.fn()
    render(
      <HitlDecisionCard
        actionRequests={[
          { name: 'shell_run', args: { command: 'ls' } },
          { name: 'shell_run', args: { command: 'pwd' } }
        ]}
        reviewConfigs={[
          {
            actionName: 'shell_run',
            allowedDecisions: ['approve', 'reject']
          }
        ]}
        onSubmit={onSubmit}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Approve all (2)' }))
    expect(onSubmit).toHaveBeenCalledWith([
      { type: 'approve' },
      { type: 'approve' }
    ])
  })

  it('submits edit payload after Apply edit', () => {
    const onSubmit = vi.fn()
    render(
      <HitlDecisionCard
        actionRequests={[
          {
            name: 'skills_manage',
            args: { action: 'install', source: 'org/repo' }
          }
        ]}
        reviewConfigs={[
          {
            actionName: 'skills_manage',
            allowedDecisions: ['approve', 'edit', 'reject']
          }
        ]}
        onSubmit={onSubmit}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Edit args' }))
    const textarea = screen.getByDisplayValue(/"action": "install"/)
    fireEvent.change(textarea, {
      target: {
        value: JSON.stringify(
          { action: 'install', source: 'org/other' },
          null,
          2
        )
      }
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply edit' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit.mock.calls[0][0]).toEqual([
      {
        type: 'edit',
        editedAction: {
          name: 'skills_manage',
          args: { action: 'install', source: 'org/other' }
        }
      }
    ])
  })
})
