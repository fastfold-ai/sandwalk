import { describe, expect, it } from 'vitest'

import {
  categorizeSkill,
  isUserCreatedSkill,
  suggestionSourceIcon,
  suggestionSourceLabel
} from '@/lib/skills-catalog-helpers'
import type { AgentSkill, AgentSkillSource } from '@sandwalk/agent-ui-core'

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

describe('suggestion source branding', () => {
  it('uses the featured Fastfold logo for fastfold-ai/skills', () => {
    const item: AgentSkillSource = {
      provider: 'Fastfold AI',
      source: 'fastfold-ai/skills',
      url: 'https://github.com/fastfold-ai/skills',
      description: 'Official Fastfold AI skills'
    }
    expect(suggestionSourceIcon(item)).toBe('/ff_simbol_color.svg')
    expect(suggestionSourceLabel(item)).toBe('Fastfold AI')
  })
})
