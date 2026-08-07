import { describe, expect, it } from 'vitest'

import { focusIsOutsideComposerDraft } from './useComposerCaret'

describe('focusIsOutsideComposerDraft', () => {
  it('treats popover/menu focus as outside the draft', () => {
    const popover = document.createElement('div')
    popover.setAttribute('data-radix-popper-content-wrapper', '')
    const input = document.createElement('input')
    popover.appendChild(input)
    document.body.appendChild(popover)

    expect(
      focusIsOutsideComposerDraft(input, () => false)
    ).toBe(true)

    popover.remove()
  })

  it('does not treat body / composer inputs as outside', () => {
    const draft = document.createElement('textarea')
    document.body.appendChild(draft)
    expect(
      focusIsOutsideComposerDraft(document.body, () => false)
    ).toBe(false)
    expect(focusIsOutsideComposerDraft(draft, node => node === draft)).toBe(
      false
    )
    draft.remove()
  })
})
