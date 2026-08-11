import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { fileChipToken } from '@/components/agents/composer-parts'
import {
  GlobalSearchDialog,
  useGlobalSearchHotkey
} from '@/components/agents/GlobalSearchDialog'
import { NewProjectDialog } from '@/components/agents/NewProjectDialog'
import { ProjectSettingsDialog } from '@/components/agents/ProjectSettingsDialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import type { CreateDraftSession } from '@/lib/draft-agent'

type AppDialogsProps = {
  client: LocalAgentClient
  navigate: NavigateFunction
  globalSearchOpen: boolean
  setGlobalSearchOpen: Dispatch<SetStateAction<boolean>>
  sessions: AgentSession[]
  sessionId: string | null
  sessionTitle: string | undefined
  activeProject: AgentProject | null
  activeProjectId: string | null
  workspaceFiles: WorkspaceFile[]
  openSessionTab: (id: string) => void
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
  setPendingOpenPath: Dispatch<SetStateAction<string | null>>
  pendingMentionRef: MutableRefObject<string | string[] | null>
  setComposer: Dispatch<SetStateAction<string>>
  setComposerFiles: Dispatch<SetStateAction<string[]>>
  createSession: CreateDraftSession
  newProjectOpen: boolean
  setNewProjectOpen: Dispatch<SetStateAction<boolean>>
  createProject: (input: {
    name: string
    description: string
    agentContext: string
  }) => Promise<void>
  projectSettingsOpen: boolean
  setProjectSettingsOpen: Dispatch<SetStateAction<boolean>>
  saveProjectSettings: (input: {
    name: string
    description: string
    agentContext: string
  }) => Promise<void>
  renameTarget: AgentSession | null
  renameValue: string
  setRenameTarget: Dispatch<SetStateAction<AgentSession | null>>
  setRenameValue: Dispatch<SetStateAction<string>>
  submitRename: () => Promise<void>
  deleteTarget: AgentSession | null
  setDeleteTarget: Dispatch<SetStateAction<AgentSession | null>>
  confirmDelete: () => Promise<void>
  batchDeletePending: boolean
  setBatchDeletePending: Dispatch<SetStateAction<boolean>>
  batchBusy: boolean
  selectedSessionIds: Set<string>
  confirmBatchDelete: () => Promise<void>
}

export function AppDialogs({
  client,
  navigate,
  globalSearchOpen,
  setGlobalSearchOpen,
  sessions,
  sessionId,
  sessionTitle,
  activeProject,
  activeProjectId,
  workspaceFiles,
  openSessionTab,
  setFilesPanelCollapsed,
  setPendingOpenPath,
  pendingMentionRef,
  setComposer,
  setComposerFiles,
  createSession,
  newProjectOpen,
  setNewProjectOpen,
  createProject,
  projectSettingsOpen,
  setProjectSettingsOpen,
  saveProjectSettings,
  renameTarget,
  renameValue,
  setRenameTarget,
  setRenameValue,
  submitRename,
  deleteTarget,
  setDeleteTarget,
  confirmDelete,
  batchDeletePending,
  setBatchDeletePending,
  batchBusy,
  selectedSessionIds,
  confirmBatchDelete
}: AppDialogsProps) {
  useGlobalSearchHotkey(globalSearchOpen, setGlobalSearchOpen)

  return (
    <>
      <GlobalSearchDialog
        open={globalSearchOpen}
        onOpenChange={setGlobalSearchOpen}
        client={client}
        sessions={sessions}
        currentSessionId={sessionId}
        currentSessionTitle={sessionTitle || activeProject?.name}
        workspaceFiles={workspaceFiles}
        onOpenSession={id => {
          openSessionTab(id)
          navigate(`/agents/${id}`)
        }}
        onOpenArtifact={(targetSessionId, path) => {
          openSessionTab(targetSessionId)
          setFilesPanelCollapsed(false)
          setPendingOpenPath(path)
          navigate(`/agents/${targetSessionId}`)
        }}
        onMentionArtifact={(targetSessionId, path) => {
          pendingMentionRef.current = path
          openSessionTab(targetSessionId)
          if (targetSessionId === sessionId) {
            setComposer(current => `${current}${fileChipToken(path)}`)
            setComposerFiles([])
            pendingMentionRef.current = null
          } else {
            navigate(`/agents/${targetSessionId}`)
          }
        }}
        onCreateSession={() => void createSession(activeProjectId)}
        onNavigate={path => navigate(path)}
      />

      <NewProjectDialog
        open={newProjectOpen}
        onOpenChange={setNewProjectOpen}
        onCreate={createProject}
      />

      <ProjectSettingsDialog
        project={activeProject}
        open={projectSettingsOpen}
        onOpenChange={setProjectSettingsOpen}
        onSave={saveProjectSettings}
      />

      <Dialog
        open={Boolean(renameTarget)}
        onOpenChange={open => {
          if (!open) {
            setRenameTarget(null)
            setRenameValue('')
          }
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Rename chat</DialogTitle>
            <DialogDescription>
              Choose a clearer name for this agent session.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={event => setRenameValue(event.target.value)}
            placeholder="Chat name"
            autoFocus
            maxLength={140}
            onKeyDown={event => {
              if (event.key === 'Enter') {
                event.preventDefault()
                void submitRename()
              }
            }}
          />
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRenameTarget(null)
                setRenameValue('')
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => void submitRename()}
              disabled={!renameValue.trim()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(deleteTarget)}
        onOpenChange={open => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent className="max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete chat?</AlertDialogTitle>
            <AlertDialogDescription>
              Delete “{deleteTarget?.title || 'Untitled session'}”? This cannot
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => void confirmDelete()}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={batchDeletePending}
        onOpenChange={open => {
          if (!open && !batchBusy) setBatchDeletePending(false)
        }}
      >
        <AlertDialogContent className="max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selectedSessionIds.size} chats?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes the selected sessions and cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={batchBusy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={batchBusy}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={event => {
                event.preventDefault()
                void confirmBatchDelete()
              }}
            >
              {batchBusy ? 'Deleting…' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
