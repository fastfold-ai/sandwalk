import { isTauri, openInSystemBrowser } from '@/lib/desktop'

export async function openMcpOAuthBrowser(
  url: string,
  onReturn?: () => void | Promise<void>
): Promise<void> {
  if (isTauri()) {
    const refresh = () => {
      window.removeEventListener('focus', refresh)
      window.setTimeout(() => void onReturn?.(), 500)
    }
    if (onReturn) window.addEventListener('focus', refresh)
    try {
      await openInSystemBrowser(url)
    } catch (error) {
      window.removeEventListener('focus', refresh)
      throw error
    }
    return
  }

  const popup = window.open(
    url,
    'fastfold-mcp-oauth',
    'width=560,height=720'
  )
  if (!popup) {
    throw new Error(
      'The browser blocked the OAuth popup. Allow popups for Sandwalk and try again.'
    )
  }
}
