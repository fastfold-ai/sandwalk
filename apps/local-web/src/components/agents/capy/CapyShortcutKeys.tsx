import { useEffect, useState } from 'react'

import {
  CAPY_SHORTCUT_CHANGE_EVENT,
  capyShortcutSymbols,
  readCapyShortcut,
  type CapyShortcut
} from '@/lib/capy-ui'

export function useCapyShortcut() {
  const [shortcut, setShortcut] = useState<CapyShortcut>(() => readCapyShortcut())
  useEffect(() => {
    const onChange = () => setShortcut(readCapyShortcut())
    window.addEventListener(CAPY_SHORTCUT_CHANGE_EVENT, onChange)
    return () => window.removeEventListener(CAPY_SHORTCUT_CHANGE_EVENT, onChange)
  }, [])
  return shortcut
}

export function CapyShortcutKeys({ className }: { className?: string }) {
  const shortcut = useCapyShortcut()
  return (
    <span
      className={`text-muted-foreground inline-flex shrink-0 items-center gap-0.5 text-xs ${className ?? ''}`}
      aria-label="Capy shortcut"
    >
      {capyShortcutSymbols(shortcut).map(symbol => (
        <span key={symbol} aria-hidden>
          {symbol}
        </span>
      ))}
    </span>
  )
}
