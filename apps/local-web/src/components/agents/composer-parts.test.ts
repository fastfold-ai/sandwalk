import { describe, expect, it } from 'vitest'

import {
  composerToMessage,
  fileChipToken,
  mcpChipToken,
  parseComposerParts,
  parseMessageParts,
  removeComposerChipAt,
  serializeComposerParts,
  skillChipToken,
  spaceAroundChips
} from './composer-parts'

describe('chip tokens', () => {
  it('builds file, skill, and mcp chip tokens', () => {
    expect(fileChipToken('src/a.ts')).toBe('⟦@:src/a.ts⟧')
    expect(skillChipToken('fold')).toBe('⟦/:fold⟧')
    expect(mcpChipToken('linear', 'Linear')).toBe(
      '⟦mcp:linear:Linear⟧'
    )
  })
})

describe('spaceAroundChips', () => {
  it('normalizes spacing around chip tokens', () => {
    expect(spaceAroundChips('hi⟦@:a.ts⟧there')).toBe('hi ⟦@:a.ts⟧ there')
    expect(spaceAroundChips('hi  ⟦/:fold⟧  x')).toBe('hi ⟦/:fold⟧ x')
    expect(spaceAroundChips(`hi${mcpChipToken('linear', 'Linear')}x`)).toBe(
      `hi ${mcpChipToken('linear', 'Linear')} x`
    )
  })
})

describe('parseComposerParts / serializeComposerParts', () => {
  it('parses text, file, skill, and mcp parts', () => {
    const value = `hello ${fileChipToken('README.md')} use ${skillChipToken('fold')} with ${mcpChipToken('linear', 'Linear')}`
    const parts = parseComposerParts(value)
    expect(parts).toEqual([
      { type: 'text', text: 'hello ' },
      { type: 'file', path: 'README.md' },
      { type: 'text', text: ' use ' },
      { type: 'skill', name: 'fold' },
      { type: 'text', text: ' with ' },
      { type: 'mcp', id: 'linear', name: 'Linear' },
      { type: 'text', text: '' }
    ])
    expect(serializeComposerParts(parts)).toBe(value)
  })

  it('returns a single empty text part for empty input', () => {
    expect(parseComposerParts('')).toEqual([{ type: 'text', text: '' }])
  })
})

describe('parseMessageParts', () => {
  it('parses plain @file, /skill, and mcp:Name mentions', () => {
    expect(
      parseMessageParts('see @src/a.ts with /fold and mcp:Linear please')
    ).toEqual([
      { type: 'text', text: 'see ' },
      { type: 'file', path: 'src/a.ts' },
      { type: 'text', text: ' with ' },
      { type: 'skill', name: 'fold' },
      { type: 'text', text: ' and ' },
      { type: 'mcp', id: 'Linear', name: 'Linear' },
      { type: 'text', text: ' please' }
    ])
  })

  it('returns content as text when there are no mentions', () => {
    expect(parseMessageParts('just text')).toEqual([
      { type: 'text', text: 'just text' }
    ])
  })

  it('does not treat URL path segments as skill mentions', () => {
    const text =
      'read this site https://news.ycombinator.com/\ngive me top 5 topics'
    expect(parseMessageParts(text)).toEqual([{ type: 'text', text }])
  })

  it('still matches a real skill next to a URL', () => {
    expect(
      parseMessageParts('use /fold on https://news.ycombinator.com/')
    ).toEqual([
      { type: 'text', text: 'use ' },
      { type: 'skill', name: 'fold' },
      { type: 'text', text: ' on https://news.ycombinator.com/' }
    ])
  })
})

describe('composerToMessage', () => {
  it('converts chips to @path /skill mcp:Name mentions with spacing', () => {
    const value = `${fileChipToken('a.ts')}${skillChipToken('fold')}${mcpChipToken('linear', 'Linear')}`
    expect(composerToMessage(value)).toBe('@a.ts /fold mcp:Linear')
  })
})

describe('removeComposerChipAt', () => {
  it('removes the chip at index and merges adjacent text', () => {
    const value = `a ${fileChipToken('one.ts')} b ${fileChipToken('two.ts')} c`
    expect(removeComposerChipAt(value, 0)).toBe('a  b ⟦@:two.ts⟧ c')
    expect(removeComposerChipAt(value, 1)).toBe('a ⟦@:one.ts⟧ b  c')
  })

  it('returns empty when all chips removed from chip-only input', () => {
    expect(removeComposerChipAt(fileChipToken('only.ts'), 0)).toBe('')
  })
})
