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
    files,
    pathDialog,
    setPathDialog,
    pathValue,
    setPathValue,
    setPathBusy,
    deleteFilePath,
    setDeleteFilePath,
    setDeleteFileBusy,
    moveSourcePath,
    setMoveSourcePath,
    setMoveBusy,
    renameDialogPath,
    setRenameDialogPath,
    renameDialogValue,
    setRenameDialogValue,
    setRenameDialogBusy,
    filesTabActive,
    setFilesTabActive,
    artifactFiles,
    isDirty,
    draftRef,
    setReloading,
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

  const reloadActiveFile = () => {
    void (async () => {
      const path = activePath
      if (!path || filesTabActive) return
      if (isDirty) {
        setStatus('Save or discard changes before reloading')
        return
      }
      setReloading(true)
      setStatus(null)
      try {
        const content = normalizeFileContent(
          await client.readFile(sessionId, path)
        )
        const next = tabsRef.current.map(tab =>
          tab.path === path ? content : tab
        )
        setTabs(next)
        tabsRef.current = next
        if (activePath === path) {
          setDraft(content.encoding === 'text' ? content.content : '')
          draftRef.current = content.encoding === 'text' ? content.content : ''
        }
      } catch (error) {
        setStatus(
          error instanceof Error ? error.message : 'Failed to reload file'
        )
      } finally {
        setReloading(false)
      }
    })()
  }

  const submitDeleteFile = async () => {
    if (!deleteFilePath) return
    const entry = files.find(item => item.path === deleteFilePath)
    const recursive = entry?.type === 'directory'
    setDeleteFileBusy(true)
    setStatus(null)
    try {
      await client.deleteFile(sessionId, deleteFilePath, recursive)
      const removed = deleteFilePath
      const prefix = `${removed}/`
      if (activePath === removed || activePath?.startsWith(prefix)) {
        await flushActiveDraft()
      }
      const next = tabsRef.current.filter(
        tab => tab.path !== removed && !tab.path.startsWith(prefix)
      )
      setTabs(next)
      tabsRef.current = next
      if (activePath === removed || activePath?.startsWith(prefix)) {
        const replacement = next[0] || null
        if (replacement) {
          setActivePath(replacement.path)
          setDraft(
            replacement.encoding === 'text' ? replacement.content : ''
          )
          setFilesTabActive(false)
        } else {
          setActivePath(null)
          setDraft('')
          setFilesTabActive(true)
        }
      }
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

  const openMoveDialog = (path: string) => {
    setMoveSourcePath(path)
  }

  const closeMoveDialog = () => {
    setMoveSourcePath(null)
  }

  const submitMoveToFolder = async (targetFolder: string) => {
    if (!moveSourcePath) return
    const name = moveSourcePath.split('/').at(-1) || moveSourcePath
    const targetPath = targetFolder ? `${targetFolder}/${name}` : name
    if (targetPath === moveSourcePath) {
      closeMoveDialog()
      return
    }
    setMoveBusy(true)
    setStatus(null)
    const previousPath = moveSourcePath
    const prefix = `${previousPath}/`
    setTabs(current =>
      current.map(tab => {
        if (tab.path === previousPath) return { ...tab, path: targetPath }
        if (tab.path.startsWith(prefix)) {
          return {
            ...tab,
            path: `${targetPath}/${tab.path.slice(prefix.length)}`
          }
        }
        return tab
      })
    )
    if (activePath === previousPath) setActivePath(targetPath)
    else if (activePath?.startsWith(prefix)) {
      setActivePath(`${targetPath}/${activePath.slice(prefix.length)}`)
    }
    try {
      await client.moveFile(sessionId, previousPath, targetPath)
      closeMoveDialog()
      await refresh()
    } catch (error) {
      setTabs(current =>
        current.map(tab => {
          if (tab.path === targetPath) return { ...tab, path: previousPath }
          if (tab.path.startsWith(`${targetPath}/`)) {
            return {
              ...tab,
              path: `${previousPath}/${tab.path.slice(targetPath.length + 1)}`
            }
          }
          return tab
        })
      )
      if (activePath === targetPath) setActivePath(previousPath)
      setStatus(error instanceof Error ? error.message : 'Failed to move file')
    } finally {
      setMoveBusy(false)
    }
  }

  const openRenameDialog = (path: string) => {
    const tab = tabs.find(item => item.path === path)
    if (tab) {
      rename.beginRenameFile(path)
      return
    }
    setRenameDialogPath(path)
    setRenameDialogValue(path.split('/').at(-1) || path)
  }

  const closeRenameDialog = () => {
    setRenameDialogPath(null)
    setRenameDialogValue('')
  }

  const submitRenameDialog = async () => {
    const previousPath = renameDialogPath
    const nextName = renameDialogValue.trim()
    if (!previousPath || !nextName) return
    if (nextName.includes('/') || nextName.includes('\\')) {
      setStatus('Enter a name without path separators.')
      return
    }
    const slash = previousPath.lastIndexOf('/')
    const dir = slash >= 0 ? previousPath.slice(0, slash) : ''
    const targetPath = dir ? `${dir}/${nextName}` : nextName
    if (targetPath === previousPath) {
      closeRenameDialog()
      return
    }
    setRenameDialogBusy(true)
    setStatus(null)
    try {
      await client.moveFile(sessionId, previousPath, targetPath)
      closeRenameDialog()
      await refresh()
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : 'Failed to rename'
      )
    } finally {
      setRenameDialogBusy(false)
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
    ).then(() => refresh())
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
    openMoveDialog,
    closeMoveDialog,
    submitMoveToFolder,
    openRenameDialog,
    closeRenameDialog,
    submitRenameDialog,
    selectFilesTab,
    selectFileTab,
    reloadActiveFile,
    downloadAll,
    downloadFile,
    handleUploadChange
  }
}
