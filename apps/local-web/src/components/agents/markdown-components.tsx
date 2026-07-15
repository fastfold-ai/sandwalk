import type { Components } from 'react-markdown'
import type { NavigateFunction } from 'react-router-dom'

import { MarkdownCodeBlock } from './markdown-code-block'

/** Static markdown element map — identity must stay stable across renders. */
export function buildMarkdownComponents(
  navigate: NavigateFunction,
  streaming: boolean
): Components {
  return {
    h1({ children }) {
      return (
        <h1 className="text-foreground mt-3 scroll-m-20 text-base font-semibold tracking-tight first:mt-0">
          {children}
        </h1>
      )
    },
    h2({ children }) {
      return (
        <h2 className="text-foreground border-border/60 mt-3 scroll-m-20 border-b pb-1 text-base font-semibold tracking-tight first:mt-0">
          {children}
        </h2>
      )
    },
    h3({ children }) {
      return (
        <h3 className="text-foreground mt-2.5 scroll-m-20 text-[15px] font-semibold tracking-tight">
          {children}
        </h3>
      )
    },
    h4({ children }) {
      return (
        <h4 className="text-foreground mt-2.5 scroll-m-20 text-[15px] font-medium tracking-tight">
          {children}
        </h4>
      )
    },
    h5({ children }) {
      return (
        <h5 className="text-foreground mt-2 scroll-m-20 text-sm font-semibold tracking-tight">
          {children}
        </h5>
      )
    },
    h6({ children }) {
      return (
        <h6 className="text-muted-foreground mt-2 scroll-m-20 text-sm font-medium tracking-tight">
          {children}
        </h6>
      )
    },
    p({ children }) {
      return (
        <p className="text-foreground text-[15px] leading-6 [&:not(:first-child)]:mt-2.5">
          {children}
        </p>
      )
    },
    strong({ children }) {
      return (
        <strong className="text-foreground font-semibold">{children}</strong>
      )
    },
    em({ children }) {
      return <em className="text-foreground italic">{children}</em>
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
      return <li className="text-foreground mt-1.5">{children}</li>
    },
    blockquote({ children }) {
      return (
        <blockquote className="text-muted-foreground border-border/70 mt-4 border-l-2 pl-4 text-[15px] italic">
          {children}
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
          {children}
        </th>
      )
    },
    td({ children }) {
      return (
        <td className="text-foreground border-border/60 border-b px-3 py-2 align-top">
          {children}
        </td>
      )
    }
  }
}
