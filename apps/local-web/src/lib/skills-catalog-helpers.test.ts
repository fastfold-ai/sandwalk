import type { AgentSkill, AgentSkillSource } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import {
  categorizeSkill,
  isUserCreatedSkill,
  skillMetaText,
  suggestionSourceIcon,
  suggestionSourceLabel
} from '@/lib/skills-catalog-helpers'

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

  it('labels bundled package skills as Built-in', () => {
    expect(
      categorizeSkill(
        skill({ name: 'skill-creator', source: 'bundled', author: 'sandwalk' })
      )
    ).toBe('Built-in')
    expect(
      categorizeSkill(
        skill({ name: 'skill-find', category: 'Built-in', author: 'sandwalk' })
      )
    ).toBe('Built-in')
    expect(
      skillMetaText(
        skill({
          name: 'skill-creator',
          source: 'bundled',
          author: 'sandwalk',
          version: '1.0.0'
        })
      )
    ).toBe('sandwalk · v1.0.0 · Built-in')
  })

  it('keeps heuristic categories for non-user skills', () => {
    expect(
      categorizeSkill(skill({ name: 'slack_report', source: 'global' }))
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
