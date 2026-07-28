import { describe, expect, it } from 'vitest'

import {
  BUNDLED_SKILLS_GITHUB_REPO,
  BUNDLED_SKILLS_GITHUB_TREE,
  catalogCoordsFromInstalledSkill,
  skillAuthorUrl,
  skillGithubUrl
} from './skills-catalog-source'

describe('bundled skill github links', () => {
  it('points built-in skills at the sandwalk package skills tree', () => {
    expect(skillGithubUrl('skill-creator', 'bundled')).toBe(
      BUNDLED_SKILLS_GITHUB_TREE
    )
    expect(skillGithubUrl('skill-find', 'bundled')).toBe(
      BUNDLED_SKILLS_GITHUB_TREE
    )
    expect(skillAuthorUrl('bundled')).toBe(BUNDLED_SKILLS_GITHUB_REPO)
    expect(
      catalogCoordsFromInstalledSkill({
        name: 'skill-find',
        source: 'bundled'
      })
    ).toBeNull()
  })

  it('keeps catalog github urls for installed fastfold skills', () => {
    expect(
      skillGithubUrl('fold', 'fastfold-ai/skills@skills/fold')
    ).toBe('https://github.com/fastfold-ai/skills/tree/main/skills/fold')
    expect(skillAuthorUrl('fastfold-ai/skills@skills/fold')).toBe(
      'https://github.com/fastfold-ai/skills'
    )
  })
})
