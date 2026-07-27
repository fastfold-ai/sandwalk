import { useEffect, useState } from 'react'

import {
  getAttentionSessionIds,
  SESSION_ATTENTION_CHANGE_EVENT
} from '@/lib/session-attention'

/** Reactive set of session ids with unread attention (Dock + in-app blue dots). */
export function useSessionAttentionIds(): ReadonlySet<string> {
  const [ids, setIds] = useState<ReadonlySet<string>>(() =>
    new Set(getAttentionSessionIds())
  )

  useEffect(() => {
    const onChange = () => setIds(new Set(getAttentionSessionIds()))
    window.addEventListener(SESSION_ATTENTION_CHANGE_EVENT, onChange)
    return () => {
      window.removeEventListener(SESSION_ATTENTION_CHANGE_EVENT, onChange)
    }
  }, [])

  return ids
}
