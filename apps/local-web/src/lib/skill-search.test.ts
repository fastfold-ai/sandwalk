import { describe, expect, it } from 'vitest'

import {
  compareSkillsBySearchRank,
  skillMatchesSearch,
  skillSearchMatchRank
} from './skill-search'

const fold = { name: 'fold', description: 'Fold proteins with SimpleFold' }
const boltz = { name: 'boltz', description: 'Structure prediction' }
const emptyDesc = { name: 'diagrams', description: '>' }

describe('skillSearchMatchRank', () => {
  it('returns neutral rank for empty query', () => {
    expect(skillSearchMatchRank(fold, '')).toBe(3)
    expect(skillSearchMatchRank(fold, '   ')).toBe(3)
  })

  it('ranks exact, prefix, substring, and description matches', () => {
    expect(skillSearchMatchRank(fold, 'fold')).toBe(0)
    expect(skillSearchMatchRank(fold, 'fo')).toBe(1)
    expect(skillSearchMatchRank(fold, 'old')).toBe(2)
    expect(skillSearchMatchRank(fold, 'fold proteins')).toBe(3)
    expect(skillSearchMatchRank(fold, 'simplefold')).toBe(4)
    expect(skillSearchMatchRank(fold, 'nomatch')).toBe(5)
  })

  it('ignores placeholder descriptions', () => {
    expect(skillSearchMatchRank(emptyDesc, 'anything')).toBe(5)
  })
})

describe('skillMatchesSearch', () => {
  it('matches everything when query is empty', () => {
    expect(skillMatchesSearch(fold, '')).toBe(true)
  })

  it('requires a rank under 5', () => {
    expect(skillMatchesSearch(fold, 'fold')).toBe(true)
    expect(skillMatchesSearch(fold, 'zzz')).toBe(false)
  })
})

describe('compareSkillsBySearchRank', () => {
  it('sorts by rank then name', () => {
    expect(compareSkillsBySearchRank(fold, boltz, 'fold')).toBeLessThan(0)
    expect(compareSkillsBySearchRank(boltz, fold, 'fold')).toBeGreaterThan(0)
    expect(compareSkillsBySearchRank(boltz, fold, 'zzz')).toBeLessThan(0)
  })
})
