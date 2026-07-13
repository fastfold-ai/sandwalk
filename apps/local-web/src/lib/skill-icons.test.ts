import { describe, expect, it } from 'vitest'

import {
  composerSkillIcon,
  featuredSkillIcon,
  isFeaturedSkill,
  skillIcon,
  skillIconInvertInDark
} from './skill-icons'

describe('isFeaturedSkill', () => {
  it('detects fastfold author, bundled source, and fastfold-ai source', () => {
    expect(
      isFeaturedSkill({ name: 'x', author: 'FastFold Team', source: 'user' })
    ).toBe(true)
    expect(
      isFeaturedSkill({ name: 'x', author: '', source: 'bundled' })
    ).toBe(true)
    expect(
      isFeaturedSkill({
        name: 'x',
        author: '',
        source: 'github:fastfold-ai/skills'
      })
    ).toBe(true)
    expect(
      isFeaturedSkill({ name: 'x', author: 'other', source: 'user' })
    ).toBe(false)
  })
})

describe('skillIcon helpers', () => {
  it('prefers custom iconSrc over built-in map', () => {
    expect(skillIcon({ name: 'boltz', iconSrc: '/custom.png' })).toBe(
      '/custom.png'
    )
    expect(skillIcon({ name: 'boltz', iconSrc: null })).toBe(
      '/pipelines/boltzgen.svg'
    )
    expect(skillIcon({ name: 'unknown', iconSrc: null })).toBeNull()
  })

  it('only inverts mapped icons without custom src', () => {
    expect(skillIconInvertInDark({ name: 'boltz', iconSrc: null })).toBe(true)
    expect(
      skillIconInvertInDark({ name: 'boltz', iconSrc: '/custom.png' })
    ).toBe(false)
    expect(
      skillIconInvertInDark({ name: 'slack_report', iconSrc: null })
    ).toBe(false)
  })

  it('featuredSkillIcon falls back to brand mark', () => {
    expect(featuredSkillIcon({ name: 'boltz', iconSrc: null })).toBe(
      '/pipelines/boltzgen.svg'
    )
    expect(featuredSkillIcon({ name: 'other', iconSrc: null })).toBe(
      '/ff_simbol_color.svg'
    )
  })

  it('composerSkillIcon uses featured fallback only for featured skills', () => {
    expect(
      composerSkillIcon({
        name: 'custom',
        iconSrc: null,
        author: 'FastFold',
        source: 'user'
      })
    ).toBe('/ff_simbol_color.svg')
    expect(
      composerSkillIcon({
        name: 'custom',
        iconSrc: null,
        author: 'other',
        source: 'user'
      })
    ).toBeNull()
    expect(
      composerSkillIcon({
        name: 'boltz',
        iconSrc: null,
        author: 'other',
        source: 'user'
      })
    ).toBe('/pipelines/boltzgen.svg')
  })
})
