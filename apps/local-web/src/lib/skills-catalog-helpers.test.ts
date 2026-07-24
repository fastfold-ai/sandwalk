import { describe, expect, it } from 'vitest'

import {
  categorizeSkill,
  isUserCreatedSkill
} from '@/lib/skills-catalog-helpers'
import type { AgentSkill } from '@sandwalk/agent-ui-core'

function skill(partial: Partial<AgentSkill>): AgentSkill {
  return {
    name: 'x',
    description: '',
    tags: [],
    source: '',
    author: '',
    version: null,
    updatedAt: null,
    iconSrc: null,
    enabled: true,
    ...partial
  }
}

describe('user-created skill labels', () => {
  it('categorizes user-created skills as Created by Me', () => {
    expect(
      categorizeSkill(
        skill({
          name: 'lab-notes',
          category: 'Created by Me',
          author: 'Julio',
          source: 'custom'
        })
      )
    ).toBe('Created by Me')
    expect(
      isUserCreatedSkill(
        skill({
          source:
            '/Users/me/.sandwalk/workspaces/abc/artifacts/skills/lab-notes',
          author: 'Custom'
        })
      )
    ).toBe(true)
  })

  it('keeps heuristic categories for non-user skills', () => {
    expect(
      categorizeSkill(skill({ name: 'slack_report', source: 'bundled' }))
    ).toBe('Integrations')
  })
})
