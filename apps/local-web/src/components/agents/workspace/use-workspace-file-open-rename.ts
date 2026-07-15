import type { WorkspaceFile } from '@sandwalk/agent-ui-core'

import { normalizeFileContent } from '../workspace-utils'

import type { WorkspacePanelState } from './use-workspace-panel-state'

export function useWorkspaceFileRenameActions(state: WorkspacePanelState) {
  const {
    client,
    sessionId,
    tabs,
    activePath,
    setActivePath,
    setDraft,
    setStatus,
    renameFilePathRef,
    renameFileValueRef,
    renameFileBusyRef,
    renameFileCancelRef,
    renameFileIgnoreBlurRef,
    renameFileInputRef,
    setRenameFilePath,
    setRenameFileValue,
    setRenameFileBusy,
    setFilesTabActive,
    setTabs,
    refresh
  } = state

  const submitRenameFile = async () => {
    const previousPath = renameFilePathRef.current
    const nextName = renameFileValueRef.current.trim()
    if (!previousPath || !nextName || renameFileBusyRef.current) return
    if (nextName.includes('/') || nextName.includes('\\')) {
      setStatus('Enter a file name without path separators.')
      return
    }
    const slash = previousPath.lastIndexOf('/')
    const dir = slash >= 0 ? previousPath.slice(0, slash) : ''
    const targetPath = dir ? `${dir}/${nextName}` : nextName
    const previousName = previousPath.split('/').at(-1) || previousPath
    if (targetPath === previousPath || nextName === previousName) {
      setRenameFilePath(null)
      setRenameFileValue('')
      return
    }
    renameFileBusyRef.current = true
    setRenameFileBusy(true)
    setStatus(null)
    setTabs(current =>
      current.map(tab =>
        tab.path === previousPath ? { ...tab, path: targetPath } : tab
      )
    )
    if (activePath === previousPath) setActivePath(targetPath)
    setRenameFilePath(null)
    setRenameFileValue('')
    try {
      await client.moveFile(sessionId, previousPath, targetPath)
      await refresh()
      try {
        const content = await client.readFile(sessionId, targetPath)
        const normalized = normalizeFileContent(content)
        setTabs(current =>
          current.map(tab => (tab.path === targetPath ? normalized : tab))
        )
        if (activePath === targetPath || activePath === previousPath) {
          setActivePath(targetPath)
          setDraft(
            normalized.encoding === 'text' ? normalized.content : ''
          )
        }
      } catch {
        // Tab path already updated; content refresh can wait.
      }
    } catch (error) {
      setTabs(current =>
        current.map(tab =>
          tab.path === targetPath ? { ...tab, path: previousPath } : tab
        )
      )
      if (activePath === targetPath) setActivePath(previousPath)
      setStatus(
        error instanceof Error ? error.message : 'Failed to rename file'
      )
    } finally {
      renameFileBusyRef.current = false
      setRenameFileBusy(false)
    }
  }

  const beginRenameFile = (path: string) => {
    const name = path.split('/').at(-1) || path
    renameFileCancelRef.current = false
    renameFileIgnoreBlurRef.current = true
    const tab = tabs.find(item => item.path === path)
    if (tab) {
      setFilesTabActive(false)
      setActivePath(tab.path)
      setDraft(tab.encoding === 'text' ? tab.content : '')
    }
    setRenameFilePath(path)
    setRenameFileValue(name)
    requestAnimationFrame(() => {
      renameFileInputRef.current?.focus()
      renameFileInputRef.current?.select()
      window.setTimeout(() => {
        renameFileIgnoreBlurRef.current = false
      }, 150)
    })
  }

  const cancelRenameFile = () => {
    renameFileCancelRef.current = true
    setRenameFilePath(null)
    setRenameFileValue('')
  }

  const commitRenameFileFromBlur = () => {
    if (renameFileBusyRef.current || renameFileIgnoreBlurRef.current) return
    if (renameFileCancelRef.current) {
      renameFileCancelRef.current = false
      return
    }
    const path = renameFilePathRef.current
    const nextName = renameFileValueRef.current.trim()
    const currentName = path?.split('/').at(-1) || path
    if (nextName && currentName && nextName !== currentName) {
      void submitRenameFile()
    } else {
      setRenameFilePath(null)
      setRenameFileValue('')
    }
  }

  return {
    submitRenameFile,
    beginRenameFile,
    cancelRenameFile,
    commitRenameFileFromBlur
  }
}

export function useWorkspaceFileOpenActions(state: WorkspacePanelState) {
  const {
    client,
    sessionId,
    setTabs,
    activePath,
    setActivePath,
    setDraft,
    setStatus,
    tabsRef,
    filesTabActive,
    setFilesTabActive,
    flushActiveDraft
  } = state

  const openFile = async (file: WorkspaceFile) => {
    if (file.type !== 'file') return

    await flushActiveDraft()

    const existing = tabsRef.current.find(tab => tab.path === file.path)
    if (existing) {
      const sameFile = existing.path === activePath && !filesTabActive
      setActivePath(existing.path)
      setFilesTabActive(false)
      if (!sameFile) {
        setDraft(existing.encoding === 'text' ? existing.content : '')
      }
      setStatus(null)
      return
    }

    setActivePath(file.path)
    setFilesTabActive(false)
    setDraft('')
    setStatus(`Opening ${file.name}…`)
    try {
      const normalized = normalizeFileContent(
        await client.readFile(sessionId, file.path)
      )
      setTabs(current => [
        ...current.filter(
          tab => tab.path !== normalized.path && tab.path !== file.path
        ),
        normalized
      ])
      setActivePath(normalized.path)
      setDraft(normalized.encoding === 'text' ? normalized.content : '')
      setStatus(null)
    } catch (cause) {
      setFilesTabActive(true)
      setStatus(cause instanceof Error ? cause.message : 'Unable to open file')
    }
  }

  return { openFile }
}
