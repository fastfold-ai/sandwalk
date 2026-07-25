import { copyViaDesktop, isTauri } from '@/lib/desktop'

/**
 * Copy text, reporting whether it actually worked.
 *
 * Three paths, because no single one is reliable everywhere. In the desktop
 * app the native shell goes first: WKWebView blocks `navigator.clipboard`
 * without a focused, permitted, secure context, and `document.execCommand` is
 * deprecated — both can fail silently, which is how a "Copied" label ends up
 * lying to the user.
 */
export async function copyText(text: string): Promise<boolean> {
  if (!text) return false

  if (isTauri() && (await copyViaDesktop(text))) {
    return true
  }

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // Fall through to the legacy path.
    }
  }

  return legacyCopy(text)
}

function legacyCopy(text: string): boolean {
  if (typeof document === 'undefined') return false
  const area = document.createElement('textarea')
  area.value = text
  // Keep it off-screen but still selectable; `display: none` cannot be copied.
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.top = '-1000px'
  area.style.opacity = '0'
  document.body.appendChild(area)
  try {
    area.select()
    area.setSelectionRange(0, text.length)
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    document.body.removeChild(area)
  }
}
