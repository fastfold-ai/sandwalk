import { Check, Copy, Maximize2, X } from 'lucide-react'
import { memo, useEffect, useMemo, useState } from 'react'
import type { Components } from 'react-markdown'
import ReactMarkdown from 'react-markdown'
import { useNavigate } from 'react-router-dom'
import type { NavigateFunction } from 'react-router-dom'
import remarkGfm from 'remark-gfm'

import {
  looksLikeMermaid,
  MermaidDiagram
} from '@/components/agents/MermaidDiagram'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function isDarkMode() {
  return document.documentElement.classList.contains('dark')
}

/**
 * Fence bare Mermaid diagrams so react-markdown treats them as code blocks.
 * Skips content already inside ``` fences.
 */
export function ensureMermaidFences(markdown: string): string {
  const lines = markdown.split('\n')
  const out: string[] = []
  let inFence = false
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    const fenceMatch = line.match(/^(\s*)(`{3,}|~{3,})(.*)$/)
    if (fenceMatch) {
      inFence = !inFence
      out.push(line)
      i += 1
      continue
    }

    if (
      !inFence &&
      looksLikeMermaid(line) &&
      (i === 0 || lines[i - 1].trim() === '')
    ) {
      const block: string[] = [line]
      i += 1
      while (i < lines.length) {
        const next = lines[i]
        if (next.match(/^(\s*)(`{3,}|~{3,})/)) break
        if (next.trim() === '' && i + 1 < lines.length) {
          const peek = lines[i + 1]
          // Blank line ends the diagram unless the next line looks like
          // continuation (edge/node syntax or indented).
          if (
            peek.trim() === '' ||
            (!/^\s/.test(peek) &&
              !/^(--|==>|-->|-\\.->|subgraph|end|style|classDef|linkStyle|%%)/i.test(
                peek.trim()
              ) &&
              !/^[A-Za-z0-9_]+\s*(\[|\(|\{|>|-->)/.test(peek.trim()))
          ) {
            break
          }
        }
        block.push(next)
        i += 1
      }
      out.push('```mermaid')
      out.push(...block)
      out.push('```')
      continue
    }

    out.push(line)
    i += 1
  }

  return out.join('\n')
}

const CodeBlock = memo(function CodeBlock({
  language,
  code,
  streaming
}: {
  language: string
  code: string
  streaming?: boolean
}) {
  const [html, setHtml] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [dark, setDark] = useState(() =>
    typeof document !== 'undefined' ? isDarkMode() : true
  )

  const isMermaid =
    language.toLowerCase() === 'mermaid' ||
    (!language && looksLikeMermaid(code))

  useEffect(() => {
    const sync = () => setDark(isDarkMode())
    sync()
    const observer = new MutationObserver(sync)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!language || isMermaid) return
    let active = true
    void import('shiki').then(({ codeToHtml }) =>
      codeToHtml(code, {
        lang: language,
        theme: dark ? 'github-dark' : 'github-light'
      }).then(value => {
        if (active) setHtml(value)
      })
    )
    return () => {
      active = false
    }
  }, [code, dark, isMermaid, language])

  if (isMermaid) {
    return (
      <MermaidDiagram
        code={code}
        streamAware={Boolean(streaming)}
        ready={!streaming}
      />
    )
  }

  const content = (
    <div className={cn('overflow-auto', fullscreen && 'h-full')}>
      {html ? (
        <div
          className="[&_code]:text-xs [&_pre]:m-0 [&_pre]:min-h-full [&_pre]:!bg-transparent [&_pre]:p-4"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre className="text-foreground m-0 overflow-auto bg-transparent p-4 text-xs">
          <code>{code}</code>
        </pre>
      )}
    </div>
  )

  return (
    <>
      <div className="bg-muted/40 text-foreground group relative my-3 overflow-hidden rounded-xl border">
        <div className="text-muted-foreground flex h-8 items-center justify-between border-b px-3 text-[11px]">
          <span className="uppercase tracking-wide">{language || 'text'}</span>
          <div className="flex items-center">
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => setFullscreen(true)}
            >
              <Maximize2 className="size-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => {
                void navigator.clipboard.writeText(code)
                setCopied(true)
                window.setTimeout(() => setCopied(false), 1200)
              }}
            >
              {copied ? (
                <Check className="size-3.5" />
              ) : (
                <Copy className="size-3.5" />
              )}
            </Button>
          </div>
        </div>
        {content}
      </div>
      {fullscreen ? (
        <div className="bg-background fixed inset-0 z-[100] flex flex-col">
          <div className="flex h-12 items-center justify-between border-b px-4">
            <span className="text-sm">{language || 'text'}</span>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setFullscreen(false)}
            >
              <X />
            </Button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">{content}</div>
        </div>
      ) : null}
    </>
  )
})

/** Static markdown element map — identity must stay stable across renders. */
function buildMarkdownComponents(
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
        <CodeBlock language={language} code={code} streaming={streaming} />
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

export const MarkdownContent = memo(function MarkdownContent({
  content,
  className,
  streaming = false
}: {
  content: string
  className?: string
  /** When true, Mermaid waits until the message finishes streaming. */
  streaming?: boolean
}) {
  const navigate = useNavigate()
  const prepared = useMemo(() => ensureMermaidFences(content), [content])
  // Keep react-markdown custom component identities stable. A fresh object
  // every render remounts Mermaid/Shiki and flickers dense assistant bubbles.
  const components = useMemo(
    () => buildMarkdownComponents(navigate, streaming),
    [navigate, streaming]
  )

  return (
    <div
      className={cn(
        'text-foreground max-w-none break-words [&_a]:underline [&_a]:underline-offset-2',
        className
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {prepared}
      </ReactMarkdown>
    </div>
  )
})
