import { describe, expect, it } from 'vitest'

import {
  computeAtFileQuery,
  computeHashChatQuery,
  computeSlashSkillQuery,
  extractSkillOverviewFromMarkdown,
  getSkillPromptExamples
} from './skill-examples'

describe('getSkillPromptExamples', () => {
  it('returns mapped examples for known skills', () => {
    const examples = getSkillPromptExamples('Boltz')
    expect(examples.length).toBeGreaterThan(0)
    expect(examples[0]?.title).toContain('Structure')
  })

  it('returns generic examples for unknown skills', () => {
    const examples = getSkillPromptExamples('custom-skill')
    expect(examples).toHaveLength(2)
    expect(examples[0]?.prompt).toContain('/custom-skill')
  })
})

describe('extractSkillOverviewFromMarkdown', () => {
  it('strips frontmatter and headings, keeping first prose lines', () => {
    const raw = `---
name: fold
---
# Fold

First sentence.

Second sentence.

Third ignored.`
    expect(extractSkillOverviewFromMarkdown(raw)).toBe(
      'First sentence. Second sentence.'
    )
  })

  it('returns null when there is no prose', () => {
    expect(extractSkillOverviewFromMarkdown('# Only heading')).toBeNull()
    expect(extractSkillOverviewFromMarkdown('')).toBeNull()
  })
})

describe('computeSlashSkillQuery', () => {
  it('detects slash queries at word boundaries', () => {
    expect(computeSlashSkillQuery('use /fo', 7)).toEqual({
      query: 'fo',
      start: 4,
      end: 7
    })
    // caret past the space after the query → null
    expect(computeSlashSkillQuery('use /fo more', 8)).toBeNull()
    expect(computeSlashSkillQuery('path/to', 7)).toBeNull()
    expect(computeSlashSkillQuery('hello', 5)).toBeNull()
  })
})

describe('computeAtFileQuery', () => {
  it('detects @file queries at word boundaries', () => {
    expect(computeAtFileQuery('open @src/', 10)).toEqual({
      query: 'src/',
      start: 5,
      end: 10
    })
    // caret past the space after the query → null
    expect(computeAtFileQuery('open @src/ a', 11)).toBeNull()
    expect(computeAtFileQuery('email@x', 7)).toBeNull()
    expect(computeAtFileQuery('hello', 5)).toBeNull()
  })
})

describe('computeHashChatQuery', () => {
  it('detects #chat mentions like @ file mentions, including at start of input', () => {
    expect(computeHashChatQuery('summarize #hi', 13)).toEqual({
      query: 'hi',
      start: 10,
      end: 13
    })
    expect(computeHashChatQuery('#EGFR', 5)).toEqual({
      query: 'EGFR',
      start: 0,
      end: 5
    })
    expect(computeHashChatQuery('#', 1)).toEqual({
      query: '',
      start: 0,
      end: 1
    })
    expect(computeHashChatQuery('foo#bar', 7)).toBeNull()
    expect(computeHashChatQuery('hello', 5)).toBeNull()
  })
})