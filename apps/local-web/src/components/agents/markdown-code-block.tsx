import { Check, Copy, Maximize2, X } from 'lucide-react'
import { memo, useEffect, useState } from 'react'

import { looksLikeMermaid, MermaidDiagram } from '@/components/agents/MermaidDiagram'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function isDarkMode() {
  return document.documentElement.classList.contains('dark')
}

export const MarkdownCodeBlock = memo(function MarkdownCodeBlock({
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
    // Highlighting a growing block on every delta is a stream-perf killer;
    // show the plain <pre> fallback and highlight once the message settles.
    if (!language || isMermaid || streaming) return
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
  }, [code, dark, isMermaid, language, streaming])

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
