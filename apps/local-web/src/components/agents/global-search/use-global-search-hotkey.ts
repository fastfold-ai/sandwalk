import { useEffect } from 'react'

export function useGlobalSearchHotkey(
  open: boolean,
  setOpen: (open: boolean) => void
) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return
      if (event.key.toLowerCase() !== 'k') return
      if (!(event.metaKey || event.ctrlKey)) return
      if (event.altKey || event.shiftKey) return
      event.preventDefault()
      setOpen(!open)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, setOpen])
}
