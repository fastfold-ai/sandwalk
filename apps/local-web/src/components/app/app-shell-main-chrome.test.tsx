import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const desktop = vi.hoisted(() => ({
  startWindowDrag: vi.fn(),
  toggleMaximize: vi.fn()
}))

vi.mock('@/lib/desktop', () => ({
  startWindowDrag: () => desktop.startWindowDrag(),
  toggleMaximize: () => desktop.toggleMaximize()
}))

import { AppShellMainDragStrip, AppShellTitleBar } from './app-shell-main-chrome'

describe('AppShellMainDragStrip', () => {
  it('starts a window drag from empty titlebar space and ignores buttons', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      left: 0,
      right: 400,
      top: 0,
      bottom: 40,
      width: 400,
      height: 40,
      x: 0,
      y: 0,
      toJSON() {
        return {}
      }
    })
    const view = render(
      <div>
        <AppShellTitleBar activeTitle="Chat" />
        <AppShellMainDragStrip />
        <button type="button">New</button>
      </div>
    )
    expect(view.getByText('Chat')).toBeTruthy()
    window.dispatchEvent(
      new PointerEvent('pointerdown', { button: 0, clientX: 10, clientY: 10, bubbles: true })
    )
    expect(desktop.startWindowDrag).toHaveBeenCalled()
    window.dispatchEvent(
      new MouseEvent('dblclick', { clientX: 10, clientY: 10, bubbles: true })
    )
    expect(desktop.toggleMaximize).toHaveBeenCalled()
    view.unmount()
  })
})
