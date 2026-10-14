import { useEffect, useState } from 'react'

import { CapyShortcutKeys } from '@/components/agents/capy/CapyShortcutKeys'
import {
  DEFAULT_CAPY_SHORTCUT,
  setCapyShortcutRecording,
  shortcutFromEvent,
  writeCapyShortcut
} from '@/lib/capy-ui'

export function CapyShortcutSetting() {
  const [recording, setRecording] = useState(false)

  useEffect(() => {
    if (!recording) return
    setCapyShortcutRecording(true)
    const onKey = (event: KeyboardEvent) => {
      event.preventDefault()
      event.stopPropagation()
      if (event.key === 'Escape') {
        setRecording(false)
        return
      }
      const next = shortcutFromEvent(event)
      if (!next) return
      writeCapyShortcut(next)
      setRecording(false)
    }
    window.addEventListener('keydown', onKey, true)
    return () => {
      setCapyShortcutRecording(false)
      window.removeEventListener('keydown', onKey, true)
    }
  }, [recording])

  return (
    <section className="space-y-3">
      <h3 className="text-base font-semibold">Capy shortcut</h3>
      <p className="text-muted-foreground text-sm">
        Opens Capy and toggles hands-free voice. Use at least two keys, such as
        Control and Option.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="border-border hover:bg-muted inline-flex min-w-28 items-center justify-center gap-1 rounded-md border px-3 py-1.5"
          onClick={() => setRecording(true)}
        >
          {recording ? (
            <span className="text-sm">Press shortcut…</span>
          ) : (
            <CapyShortcutKeys className="text-sm" />
          )}
        </button>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground text-sm"
          onClick={() => writeCapyShortcut({ ...DEFAULT_CAPY_SHORTCUT })}
        >
          Reset
        </button>
      </div>
    </section>
  )
}
