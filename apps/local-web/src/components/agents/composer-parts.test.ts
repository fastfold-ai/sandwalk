import { describe, expect, it } from 'vitest'

import {
  composerToMessage,
  fileChipToken,
  parseComposerParts,
  parseMessageParts,
  removeComposerChipAt,
  serializeComposerParts,
  skillChipToken,
  spaceAroundChips
} from './composer-parts'

describe('chip tokens', () => {
  it('builds file and skill chip tokens', () => {
    expect(fileChipToken('src/a.ts')).toBe('⟦@:src/a.ts⟧')
    expect(skillChipToken('fold')).toBe('⟦/:fold⟧')
  })
})

describe('spaceAroundChips', () => {
  it('normalizes spacing around chip tokens', () => {
    expect(spaceAroundChips('hi⟦@:a.ts⟧there')).toBe('hi ⟦@:a.ts⟧ there')
    expect(spaceAroundChips('hi  ⟦/:fold⟧  x')).toBe('hi ⟦/:fold⟧ x')
  })
})

describe('parseComposerParts / serializeComposerParts', () => {
  it('parses text, file, and skill parts', () => {
    const value = `hello ${fileChipToken('README.md')} use ${skillChipToken('fold')}`
    const parts = parseComposerParts(value)
    expect(parts).toEqual([
      { type: 'text', text: 'hello ' },
      { type: 'file', path: 'README.md' },
      { type: 'text', text: ' use ' },
      { type: 'skill', name: 'fold' },
      { type: 'text', text: '' }
    ])
    expect(serializeComposerParts(parts)).toBe(value)
  })

  it('returns a single empty text part for empty input', () => {
    expect(parseComposerParts('')).toEqual([{ type: 'text', text: '' }])
  })
})

describe('parseMessageParts', () => {
  it('parses plain @file and /skill mentions', () => {
    expect(parseMessageParts('see @src/a.ts with /fold please')).toEqual([
      { type: 'text', text: 'see ' },
      { type: 'file', path: 'src/a.ts' },
      { type: 'text', text: ' with ' },
      { type: 'skill', name: 'fold' },
      { type: 'text', text: ' please' }
    ])
  })

  it('returns content as text when there are no mentions', () => {
    expect(parseMessageParts('just text')).toEqual([
      { type: 'text', text: 'just text' }
    ])
  })
})

describe('composerToMessage', () => {
  it('converts chips to @path /skill mentions with spacing', () => {
    const value = `${fileChipToken('a.ts')}${skillChipToken('fold')}`
    expect(composerToMessage(value)).toBe('@a.ts /fold')
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
