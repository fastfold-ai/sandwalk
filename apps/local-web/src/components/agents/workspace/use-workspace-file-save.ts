import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useCallback,
  useEffect
} from 'react'

import {
  AUTOSAVE_DELAY_MS,
  isStructure
} from '../workspace-utils'

type SaveArgs = {
  client: LocalAgentClient
  sessionId: string
  activePath: string | null
  active: WorkspaceFileContent | null
  isDirty: boolean
  draft: string
  draftRef: MutableRefObject<string>
  savingRef: MutableRefObject<boolean>
  tabsRef: MutableRefObject<WorkspaceFileContent[]>
  setTabs: Dispatch<SetStateAction<WorkspaceFileContent[]>>
  setDraft: Dispatch<SetStateAction<string>>
  setStatus: Dispatch<SetStateAction<string | null>>
  setSaving: Dispatch<SetStateAction<boolean>>
  refresh: () => Promise<void>
}

export function useWorkspaceFileSave({
  client,
  sessionId,
  activePath,
  active,
  isDirty,
  draft,
  draftRef,
  savingRef,
  tabsRef,
  setTabs,
  setDraft,
  setStatus,
  setSaving,
  refresh
}: SaveArgs) {
  const saveFile = useCallback(
    async (
      path: string,
      content: string,
      baseVersion: string | null | undefined,
      opts?: { auto?: boolean }
    ) => {
      if (savingRef.current) return false
      savingRef.current = true
      setSaving(true)
      if (!opts?.auto) setStatus('Saving…')
      try {
        const result = await client.writeFile(sessionId, {
          path,
          content,
          baseVersion
        })
        if (!result.ok) {
          setTabs(current => {
            const next = current.map(tab =>
              tab.path === result.current.path ? result.current : tab
            )
            tabsRef.current = next
            return next
          })
          setDraft(result.current.content)
          setStatus('File changed on disk; latest version loaded.')
          return false
        }
        setTabs(current => {
          const next = current.map(tab =>
            tab.path === result.content.path ? result.content : tab
          )
          tabsRef.current = next
          return next
        })
        setDraft(current =>
          current === content ? result.content.content : current
        )
        setStatus('Saved')
        window.setTimeout(() => {
          setStatus(current => (current === 'Saved' ? null : current))
        }, 1500)
        void refresh()
        return true
      } catch (cause) {
        setStatus(cause instanceof Error ? cause.message : 'Save failed')
        return false
      } finally {
        savingRef.current = false
        setSaving(false)
      }
    },
    [
      client,
      refresh,
      savingRef,
      sessionId,
      setDraft,
      setSaving,
      setStatus,
      setTabs,
      tabsRef
    ]
  )

  const flushActiveDraft = useCallback(async () => {
    if (!activePath) return
    const tab = tabsRef.current.find(item => item.path === activePath)
    if (!tab || tab.encoding !== 'text' || isStructure(tab.path)) return
    const content = draftRef.current
    if (content === tab.content) return
    await saveFile(tab.path, content, tab.version, { auto: true })
  }, [activePath, draftRef, saveFile, tabsRef])

  const save = useCallback(async () => {
    if (!activePath) return
    const tab = tabsRef.current.find(item => item.path === activePath)
    if (!tab || tab.encoding !== 'text' || isStructure(tab.path)) return
    const content = draftRef.current
    if (content === tab.content) {
      setStatus('Saved')
      window.setTimeout(() => {
        setStatus(current => (current === 'Saved' ? null : current))
      }, 1200)
      return
    }
    await saveFile(tab.path, content, tab.version)
  }, [activePath, draftRef, saveFile, setStatus, tabsRef])

  useEffect(() => {
    if (!isDirty || !active) return
    const path = active.path
    const version = active.version
    const timer = window.setTimeout(() => {
      void saveFile(path, draftRef.current, version, { auto: true })
    }, AUTOSAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [active, draftRef, isDirty, draft, saveFile])

  useEffect(() => {
    if (!isDirty) return
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [isDirty])

  return { saveFile, flushActiveDraft, save }
}
