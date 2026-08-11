/** Custom MIME for dragging workspace file/folder refs into the composer. */
export const WORKSPACE_PATH_MIME = 'application/x-sandwalk-workspace-path'

export type WorkspacePathDragPayload = {
  path: string
  type: 'file' | 'directory'
}

export function setWorkspacePathDragData(
  dataTransfer: DataTransfer,
  payload: WorkspacePathDragPayload
) {
  dataTransfer.setData(WORKSPACE_PATH_MIME, JSON.stringify(payload))
  dataTransfer.setData('text/plain', payload.path)
  dataTransfer.effectAllowed = 'copy'
}

export function getWorkspacePathDragData(
  dataTransfer: DataTransfer | null | undefined
): WorkspacePathDragPayload | null {
  const raw = dataTransfer?.getData(WORKSPACE_PATH_MIME)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as WorkspacePathDragPayload
    if (!parsed?.path || (parsed.type !== 'file' && parsed.type !== 'directory')) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function dragHasWorkspacePath(
  event: { dataTransfer?: DataTransfer | null }
): boolean {
  const types = event.dataTransfer?.types
  if (!types) return false
  return Array.from(types).includes(WORKSPACE_PATH_MIME)
}
