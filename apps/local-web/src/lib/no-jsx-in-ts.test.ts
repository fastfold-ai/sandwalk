import { describe, expect, it } from 'vitest'

// Eager raw imports so this runs in the browser vitest env (no Node fs types).
const tsSources = import.meta.glob(['../**/*.ts', '!**/*.d.ts'], {
  eager: true,
  query: '?raw',
  import: 'default'
}) as Record<string, string>

describe('no JSX in .ts files', () => {
  it('keeps JSX only in .tsx so Vite/oxc can parse modules', () => {
    const offenders: string[] = []
    for (const [path, text] of Object.entries(tsSources)) {
      if (path.endsWith('.test.ts')) continue
      const lines = text.split(/\r?\n/)
      for (let i = 0; i < lines.length; i += 1) {
        const line = lines[i]
        if (
          /return\s+</.test(line) ||
          /<\s*(?:div|span|img|button|svg|Icon|Link|Fragment)\b/.test(line)
        ) {
          offenders.push(`${path}:${i + 1}: ${line.trim()}`)
        }
      }
    }
    expect(offenders, offenders.join('\n')).toEqual([])
  })
})
