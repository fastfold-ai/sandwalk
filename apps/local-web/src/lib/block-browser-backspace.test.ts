import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  installBlockBrowserBackspace,
  isTypingTarget
} from './block-browser-backspace'

describe('isTypingTarget', () => {
  it('treats inputs and contenteditable as typing targets', () => {
    const input = document.createElement('input')
    const area = document.createElement('textarea')
    const editable = document.createElement('div')
    editable.setAttribute('contenteditable', 'true')
    const plain = document.createElement('div')
    expect(isTypingTarget(input)).toBe(true)
    expect(isTypingTarget(area)).toBe(true)
    expect(isTypingTarget(editable)).toBe(true)
    expect(isTypingTarget(plain)).toBe(false)
  })
})

describe('installBlockBrowserBackspace', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('prevents bare Backspace outside editable fields', () => {
    const dispose = installBlockBrowserBackspace()
    const event = new KeyboardEvent('keydown', {
      key: 'Backspace',
      bubbles: true,
      cancelable: true
    })
    const prevent = vi.spyOn(event, 'preventDefault')
    window.dispatchEvent(event)
    expect(prevent).toHaveBeenCalled()
    dispose()
  })

  it('allows Backspace inside an input', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    const dispose = installBlockBrowserBackspace()
    const event = new KeyboardEvent('keydown', {
      key: 'Backspace',
      bubbles: true,
      cancelable: true
    })
    const prevent = vi.spyOn(event, 'preventDefault')
    input.dispatchEvent(event)
    expect(prevent).not.toHaveBeenCalled()
    dispose()
  })
})
