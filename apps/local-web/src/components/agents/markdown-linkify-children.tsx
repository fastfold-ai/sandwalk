import type { AgentSession } from '@sandwalk/agent-ui-core'
import { Children, Fragment, type ReactNode } from 'react'

import { ComposerChatChip } from '@/components/agents/composer/ComposerChip'
import { splitTextWithChatMentions } from '@/components/agents/composer-parts'
import {
  type SkillIconSkill,
  SkillMentionChip} from '@/components/agents/SkillMentionChip'
import { WorkspaceFileChip } from '@/components/agents/WorkspaceFileChip'
import { splitTextWithSkillMentions } from '@/lib/skill-mentions'
import { splitTextWithWorkspacePaths } from '@/lib/workspace-file-paths'

function linkifySkillSegments(
  text: string,
  skills?: SkillIconSkill[],
  mentionChats?: AgentSession[]
): ReactNode[] {
  const chatParts = splitTextWithChatMentions(text)
  return chatParts.flatMap((chatPart, chatIndex) => {
    if (chatPart.type === 'chat') {
      const title = mentionChats?.find(chat => chat.id === chatPart.sessionId)
        ?.title
      return [
        <ComposerChatChip
          key={`ch-${chatIndex}-${chatPart.sessionId}`}
          sessionId={chatPart.sessionId}
          title={title}
        />
      ]
    }
    const skillParts = splitTextWithSkillMentions(chatPart.text)
    return skillParts.map((part, partIndex) => {
      if (part.type === 'text') {
        return (
          <Fragment key={`st-${chatIndex}-${partIndex}`}>{part.text}</Fragment>
        )
      }
      return (
        <SkillMentionChip
          key={`sk-${chatIndex}-${partIndex}-${part.name}`}
          name={part.name}
          skills={skills}
        />
      )
    })
  })
}

/** Replace workspace paths and skill mentions in markdown text children. */
export function linkifyWorkspacePathChildren(
  children: ReactNode,
  onOpenFile?: (path: string) => void,
  workspacePath?: string | null,
  skills?: SkillIconSkill[],
  mentionChats?: AgentSession[]
): ReactNode {
  return Children.map(children, (child, index) => {
    if (typeof child !== 'string') return child

    if (onOpenFile) {
      const parts = splitTextWithWorkspacePaths(child, workspacePath)
      const hasFile = parts.some(part => part.type === 'file')
      if (hasFile) {
        return (
          <Fragment key={`ws-${index}`}>
            {parts.map((part, partIndex) => {
              if (part.type === 'text') {
                return (
                  <Fragment key={`t-${partIndex}`}>
                    {linkifySkillSegments(part.text, skills, mentionChats)}
                  </Fragment>
                )
              }
              return (
                <WorkspaceFileChip
                  key={`f-${partIndex}-${part.relative}`}
                  path={part.relative}
                  onOpenFile={onOpenFile}
                />
              )
            })}
          </Fragment>
        )
      }
    }

    const chatParts = splitTextWithChatMentions(child)
    const skillParts = splitTextWithSkillMentions(child)
    if (
      chatParts.length === 1 &&
      chatParts[0]?.type === 'text' &&
      skillParts.length === 1 &&
      skillParts[0]?.type === 'text'
    ) {
      return child
    }
    return (
      <Fragment key={`sk-wrap-${index}`}>
        {linkifySkillSegments(child, skills, mentionChats)}
      </Fragment>
    )
  })
}
