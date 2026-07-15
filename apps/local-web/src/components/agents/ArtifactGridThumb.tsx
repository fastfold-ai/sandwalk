import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFile } from '@sandwalk/agent-ui-core'

import {
  IconFallback,
  ImageThumb,
  StructureThumb,
  TableThumb,
  TextThumb
} from './artifact-grid-thumb-parts'
import { classify } from './artifact-grid-thumb-utils'

export function ArtifactGridThumb({
  client,
  sessionId,
  file
}: {
  client: LocalAgentClient
  sessionId: string
  file: WorkspaceFile
}) {
  const kind = classify(file.name)

  return (
    <div className="bg-muted/25 relative aspect-[4/3] w-full overflow-hidden rounded-md border border-transparent">
      {kind === 'icon' ? (
        <IconFallback name={file.name} />
      ) : kind === 'image' ? (
        <ImageThumb
          client={client}
          sessionId={sessionId}
          path={file.path}
          name={file.name}
        />
      ) : kind === 'structure' ? (
        <StructureThumb
          client={client}
          sessionId={sessionId}
          path={file.path}
          name={file.name}
        />
      ) : kind === 'table' ? (
        <TableThumb
          client={client}
          sessionId={sessionId}
          path={file.path}
          name={file.name}
        />
      ) : (
        <TextThumb
          client={client}
          sessionId={sessionId}
          path={file.path}
          name={file.name}
        />
      )}
    </div>
  )
}
