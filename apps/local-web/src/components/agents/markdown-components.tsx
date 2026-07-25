import type { ReactNode } from 'react'
import type { Components } from 'react-markdown'
import type { NavigateFunction } from 'react-router-dom'

import {
  type SkillIconSkill,
  SkillMentionChip} from '@/components/agents/SkillMentionChip'
import { WorkspaceFileChip } from '@/components/agents/WorkspaceFileChip'
import { splitTextWithSkillMentions } from '@/lib/skill-mentions'
import { workspaceRelativeFromPath } from '@/lib/workspace-file-paths'

import { MarkdownCodeBlock } from './markdown-code-block'
import { linkifyWorkspacePathChildren } from './markdown-linkify-children'

export type MarkdownComponentOptions = {
  navigate: NavigateFunction
  streaming: boolean
  onOpenFile?: (path: string) => void
  workspacePath?: string | null
  skills?: SkillIconSkill[]
}

/** Static markdown element map — identity must stay stable across renders. */
export function buildMarkdownComponents({
  navigate,
  streaming,
  onOpenFile,
  workspacePath,
  skills
}: MarkdownComponentOptions): Components {
  const linkify = (children: ReactNode) =>
    linkifyWorkspacePathChildren(children, onOpenFile, workspacePath, skills)

  return {
    h1({ children }) {
      return (
        <h1 className="text-foreground mt-3 scroll-m-20 text-base font-semibold tracking-tight first:mt-0">
          {linkify(children)}
        </h1>
      )
    },
    h2({ children }) {
      return (
        <h2 className="text-foreground border-border/60 mt-3 scroll-m-20 border-b pb-1 text-base font-semibold tracking-tight first:mt-0">
          {linkify(children)}
        </h2>
      )
    },
    h3({ children }) {
      return (
        <h3 className="text-foreground mt-2.5 scroll-m-20 text-[15px] font-semibold tracking-tight">
          {linkify(children)}
        </h3>
      )
    },
    h4({ children }) {
      return (
        <h4 className="text-foreground mt-2.5 scroll-m-20 text-[15px] font-medium tracking-tight">
          {linkify(children)}
        </h4>
      )
    },
    h5({ children }) {
      return (
        <h5 className="text-foreground mt-2 scroll-m-20 text-sm font-semibold tracking-tight">
          {linkify(children)}
        </h5>
      )
    },
    h6({ children }) {
      return (
        <h6 className="text-muted-foreground mt-2 scroll-m-20 text-sm font-medium tracking-tight">
          {linkify(children)}
        </h6>
      )
    },
    p({ children }) {
      return (
        <p
          className={
            streaming
              ? 'text-foreground text-[15px] leading-7 [&:not(:first-child)]:mt-3.5'
              : 'text-foreground text-[15px] leading-6 [&:not(:first-child)]:mt-2.5'
          }
        >
          {linkify(children)}
        </p>
      )
    },
    strong({ children }) {
      return (
        <strong className="text-foreground font-semibold">
          {linkify(children)}
        </strong>
      )
    },
    em({ children }) {
      return (
        <em className="text-foreground italic">{linkify(children)}</em>
      )
    },
    a({ href, children }) {
      const isInternal = typeof href === 'string' && href.startsWith('/')
      if (isInternal) {
        return (
          <a
            href={href}
            className="text-foreground font-medium"
            onClick={event => {
              event.preventDefault()
              navigate(href)
            }}
          >
            {children}
          </a>
        )
      }
      return (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="text-foreground font-medium"
        >
          {children}
        </a>
      )
    },
    ul({ children }) {
      return (
        <ul className="text-foreground my-3 ml-5 list-disc text-[15px] leading-6">
          {children}
        </ul>
      )
    },
    ol({ children }) {
      return (
        <ol className="text-foreground my-3 ml-5 list-decimal text-[15px] leading-6">
          {children}
        </ol>
      )
    },
    li({ children }) {
      return (
        <li className="text-foreground mt-1.5">{linkify(children)}</li>
      )
    },
    blockquote({ children }) {
      return (
        <blockquote className="text-muted-foreground border-border/70 mt-4 border-l-2 pl-4 text-[15px] italic">
          {linkify(children)}
        </blockquote>
      )
    },
    hr() {
      return <hr className="border-border my-4" />
    },
    code({ className: codeClassName, children }) {
      const language = /language-([\w-]+)/.exec(codeClassName || '')?.[1] || ''
      const code = String(children).replace(/\n$/, '')
      if (!codeClassName && !code.includes('\n')) {
        const relative = onOpenFile
          ? workspaceRelativeFromPath(code, workspacePath)
          : null
        if (relative && onOpenFile) {
          return (
            <WorkspaceFileChip path={relative} onOpenFile={onOpenFile} />
          )
        }
        const skillParts = splitTextWithSkillMentions(code)
        if (
          skillParts.length === 1 &&
          skillParts[0]?.type === 'skill'
        ) {
          return (
            <SkillMentionChip name={skillParts[0].name} skills={skills} />
          )
        }
        return (
          <code className="bg-muted text-foreground rounded px-[0.3rem] py-[0.2rem] font-mono text-[0.9em]">
            {children}
          </code>
        )
      }
      return (
        <MarkdownCodeBlock language={language} code={code} streaming={streaming} />
      )
    },
    pre({ children }) {
      return <>{children}</>
    },
    table({ children }) {
      return (
        <div className="border-border my-3 overflow-x-auto rounded-md border">
          <table className="text-foreground w-full border-collapse text-[15px]">
            {children}
          </table>
        </div>
      )
    },
    thead({ children }) {
      return <thead className="bg-muted/50">{children}</thead>
    },
    th({ children }) {
      return (
        <th className="text-foreground border-border border-b px-3 py-2 text-left font-medium">
          {linkify(children)}
        </th>
      )
    },
    td({ children }) {
      return (
        <td className="text-foreground border-border/60 border-b px-3 py-2 align-top">
          {linkify(children)}
        </td>
      )
    }
  }
}
