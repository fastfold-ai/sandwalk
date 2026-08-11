import { looksLikeMermaid } from '@/components/agents/MermaidDiagram'

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
