import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const register = vi.fn(() => () => undefined)

vi.mock('./terminal-layer-registry', () => ({
  useTerminalLayer: () => ({ registerPlaceholder: register })
}))

import { TerminalPlaceholder } from './TerminalPlaceholder'

describe('TerminalPlaceholder', () => {
  it('registers its node and unregisters on unmount', () => {
    const onFocus = vi.fn()
    const view = render(
      <TerminalPlaceholder terminalId="term_1" onFocus={onFocus} />
    )
    expect(view.container.querySelector('[data-terminal-placeholder="term_1"]')).toBeTruthy()
    const entry = register.mock.calls[0]?.[1] as {
      onFocus: () => void
      onContextMenu: (event: MouseEvent) => void
    }
    entry.onFocus()
    expect(onFocus).toHaveBeenCalled()
    entry.onContextMenu(new MouseEvent('contextmenu'))
    view.unmount()
  })
})
