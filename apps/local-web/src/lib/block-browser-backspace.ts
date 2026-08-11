/**
 * WKWebView / Safari still map bare Backspace to history.back() when focus is
 * outside an editable field. That feels like a broken app in Sandwalk.
 *
 * Note: on macOS, any keypress hides the mouse cursor until you move the mouse
 * — that is system behavior, not something this guard can (or should) undo.
 */

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false
  const el =
    target instanceof HTMLElement
      ? target
      : target.parentElement instanceof HTMLElement
        ? target.parentElement
        : null
  if (!el) return false
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
    return true
  }
  if (el.isContentEditable) return true
  const editableHost = el.closest('[contenteditable]')
  if (editableHost instanceof HTMLElement) {
    const editable = (
      editableHost.getAttribute('contenteditable') || ''
    ).toLowerCase()
    if (editable !== 'false') return true
  }
  return Boolean(el.closest('[role="textbox"]'))
}

/** Install capture-phase guard. Returns disposer. */
export function installBlockBrowserBackspace(): () => void {
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== 'Backspace') return
    if (event.metaKey || event.ctrlKey || event.altKey) return
    if (isTypingTarget(event.target)) return
    // Stop WKWebView history navigation without stealing editor Backspace.
    event.preventDefault()
  }
  window.addEventListener('keydown', onKeyDown, true)
  return () => window.removeEventListener('keydown', onKeyDown, true)
}
