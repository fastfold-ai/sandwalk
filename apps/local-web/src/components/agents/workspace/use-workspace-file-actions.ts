import { useEffect } from 'react'

import { normalizeFileContent } from '../workspace-utils'

import type { WorkspacePanelState } from './use-workspace-panel-state'
import {
  useWorkspaceFileOpenActions,
  useWorkspaceFileRenameActions
} from './use-workspace-file-open-rename'

export function useWorkspaceFileActions(
  state: WorkspacePanelState,
  {
    openPathRequest = null,
    onOpenPathRequestHandled
  }: {
    openPathRequest?: string | null
    onOpenPathRequestHandled?: () => void
  }
) {
  const rename = useWorkspaceFileRenameActions(state)
  const open = useWorkspaceFileOpenActions(state)

  const {
    client,
    sessionId,
    tabs,
    setTabs,
    activePath,
    setActivePath,
    setDraft,
    setStatus,
    tabsRef,
    pathDialog,
    setPathDialog,
    pathValue,
    setPathValue,
    setPathBusy,
    deleteFilePath,
    setDeleteFilePath,
    setDeleteFileBusy,
    filesTabActive,
    setFilesTabActive,
    artifactFiles,
    refresh,
    flushActiveDraft
  } = state

  useEffect(() => {
    if (!openPathRequest) return
    let cancelled = false
    void (async () => {
      try {
        const list =
          state.files.length > 0
            ? state.files
            : await client.listFiles(sessionId)
        if (cancelled) return
        const match =
          list.find(
            file => file.type === 'file' && file.path === openPathRequest
          ) ||
          list.find(
            file =>
              file.type === 'file' &&
              (file.name === openPathRequest ||
                file.path.endsWith(`/${openPathRequest}`))
          )
        if (match) await open.openFile(match)
        else {
          const normalized = normalizeFileContent(
            await client.readFile(sessionId, openPathRequest)
          )
          if (cancelled) return
          setTabs(current => [
            ...current.filter(tab => tab.path !== normalized.path),
            normalized
          ])
          setActivePath(normalized.path)
          setDraft(normalized.encoding === 'text' ? normalized.content : '')
          setFilesTabActive(false)
        }
      } catch (cause) {
        if (!cancelled) {
          setStatus(
            cause instanceof Error ? cause.message : 'Unable to open file'
          )
        }
      } finally {
        if (!cancelled) onOpenPathRequestHandled?.()
      }
    })()
    return () => {
      cancelled = true
    }
  }, [openPathRequest])

  const openPathDialog = (kind: 'file' | 'folder') => {
    setPathDialog(kind)
    setPathValue('')
  }

  const closePathDialog = () => {
    setPathDialog(null)
    setPathValue('')
  }

  const submitPathDialog = async () => {
    const path = pathValue.trim()
    if (!path || !pathDialog) return
    setPathBusy(true)
    try {
      if (pathDialog === 'file') {
        await client.writeFile(sessionId, { path, content: '' })
        await refresh()
        const file = (await client.listFiles(sessionId)).find(
          item => item.path === path
        )
        if (file) await open.openFile(file)
      } else {
        await client.createFolder(sessionId, path)
        await refresh()
      }
      closePathDialog()
    } catch (cause) {
      setStatus(
        cause instanceof Error ? cause.message : 'Unable to create path'
      )
    } finally {
      setPathBusy(false)
    }
  }

  const closeTab = (path: string) => {
    void (async () => {
      if (path === activePath) await flushActiveDraft()
      const index = tabs.findIndex(tab => tab.path === path)
      const next = tabs.filter(tab => tab.path !== path)
      setTabs(next)
      if (activePath === path) {
        if (!filesTabActive) {
          const replacement = next[Math.max(0, index - 1)] || null
          if (replacement) {
            setActivePath(replacement.path)
            setDraft(
              replacement.encoding === 'text' ? replacement.content : ''
            )
          } else {
            setActivePath(null)
            setDraft('')
            setFilesTabActive(true)
          }
        } else if (!next.some(tab => tab.path === path)) {
          if (next.length === 0) setActivePath(null)
        }
      }
    })()
  }

  const closeOtherTabs = (keepPath: string) => {
    void (async () => {
      if (activePath !== keepPath) await flushActiveDraft()
      const keep = tabsRef.current.find(tab => tab.path === keepPath)
      if (!keep) return
      setTabs([keep])
      tabsRef.current = [keep]
      setFilesTabActive(false)
      setActivePath(keep.path)
      setDraft(keep.encoding === 'text' ? keep.content : '')
    })()
  }

  const downloadFileTab = (path: string) => {
    const name = path.split('/').at(-1) || path
    const anchor = document.createElement('a')
    anchor.href = client.downloadUrl(sessionId, path)
    anchor.download = name
    anchor.click()
  }

  const submitDeleteFile = async () => {
    if (!deleteFilePath) return
    setDeleteFileBusy(true)
    setStatus(null)
    try {
      await client.deleteFile(sessionId, deleteFilePath)
      closeTab(deleteFilePath)
      setDeleteFilePath(null)
      await refresh()
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : 'Failed to delete file'
      )
    } finally {
      setDeleteFileBusy(false)
    }
  }

  const selectFilesTab = () => {
    void (async () => {
      await flushActiveDraft()
      setFilesTabActive(true)
    })()
  }

  const selectFileTab = (path: string) => {
    void (async () => {
      if (path !== activePath) await flushActiveDraft()
      const tab = tabsRef.current.find(item => item.path === path)
      if (!tab) return
      setFilesTabActive(false)
      setActivePath(tab.path)
      setDraft(tab.encoding === 'text' ? tab.content : '')
    })()
  }

  const downloadAll = () => {
    for (const file of artifactFiles) {
      const anchor = document.createElement('a')
      anchor.href = client.downloadUrl(sessionId, file.path)
      anchor.download = file.name
      anchor.click()
    }
  }

  const downloadFile = (path: string) => {
    const anchor = document.createElement('a')
    anchor.href = client.downloadUrl(sessionId, path)
    anchor.download = path.split('/').at(-1) || path
    anchor.click()
  }

  const handleUploadChange = (uploads: FileList | null) => {
    const items = Array.from(uploads || [])
    void Promise.all(
      items.map(file => client.uploadFile(sessionId, file, 'uploads'))
    ).then(refresh)
  }

  return {
    openFile: open.openFile,
    openPathDialog,
    closePathDialog,
    submitPathDialog,
    closeTab,
    closeOtherTabs,
    downloadFileTab,
    submitRenameFile: rename.submitRenameFile,
    beginRenameFile: rename.beginRenameFile,
    cancelRenameFile: rename.cancelRenameFile,
    commitRenameFileFromBlur: rename.commitRenameFileFromBlur,
    submitDeleteFile,
    selectFilesTab,
    selectFileTab,
    downloadAll,
    downloadFile,
    handleUploadChange
  }
}
