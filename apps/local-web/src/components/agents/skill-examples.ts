export type SkillPromptExample = {
  title: string
  prompt: string
}

const SKILL_PROMPT_EXAMPLES: Record<string, SkillPromptExample[]> = {
  boltz: [
    {
      title: 'Structure and binding (SAB)',
      prompt:
        'Run a simple ROR1-style Boltz-2 structure-and-binding smoke test with aspirin; estimate first, then execute.'
    },
    {
      title: 'Protein design',
      prompt:
        'Run a minimal AMBP-style protein design job with 10 proteins and return top metrics plus artifact paths.'
    }
  ],
  fold: [
    {
      title: 'SimpleFold 100M',
      prompt: 'Find 4KW4 on PDB and fold it with SimpleFold 100M model'
    },
    {
      title: 'ESM1b + OpenFold',
      prompt: 'Get 6MBC from PDB and fold it with ESM1b default model'
    }
  ],
  protein_design_boltzgen: [
    {
      title: 'Quick binder design',
      prompt:
        'Show BoltzGen examples and run a minimal binder design smoke test with one target and one budget.'
    },
    {
      title: 'Draft then execute',
      prompt:
        'Prepare a BoltzGen draft from preset examples, show me the draft, then execute after confirmation.'
    }
  ],
  md_openmm_calvados: [
    {
      title: 'OpenMM from fold',
      prompt:
        'Run a CALVADOS+OpenMM simulation from my completed fold job and return metrics, plots, and artifact links.'
    },
    {
      title: 'Manual PDB+PAE input',
      prompt:
        'Submit an md_openmm_calvados run from manual PDB + PAE inputs and wait until completion.'
    }
  ],
  diagrams_mermaid: [
    {
      title: 'Workflow diagram',
      prompt:
        'Generate a Mermaid flowchart for this end-to-end pipeline and explain each stage briefly.'
    },
    {
      title: 'Sequence diagram',
      prompt:
        'Create a Mermaid sequence diagram for this API workflow with retries and error handling paths.'
    }
  ]
}

export function getSkillPromptExamples(
  skillName: string
): SkillPromptExample[] {
  const key = String(skillName || '')
    .trim()
    .toLowerCase()
  const mapped = SKILL_PROMPT_EXAMPLES[key]
  if (mapped && mapped.length > 0) return mapped
  const label = key || 'skill'
  return [
    {
      title: 'Quick start',
      prompt: `Show me a quick start example for /${label} and run a small smoke test.`
    },
    {
      title: 'End-to-end run',
      prompt: `Use /${label} end-to-end and summarize outputs with links.`
    }
  ]
}

export function extractSkillOverviewFromMarkdown(raw: string): string | null {
  const withoutFrontmatter = String(raw || '').replace(
    /^---\r?\n[\s\S]*?\r?\n---\r?\n?/,
    ''
  )
  const lines: string[] = []
  for (const line of withoutFrontmatter.split('\n')) {
    const candidate = line.trim()
    if (!candidate) continue
    if (candidate.startsWith('#')) continue
    lines.push(candidate)
    if (lines.length >= 2) break
  }
  if (lines.length === 0) return null
  return lines.join(' ')
}

export function computeSlashSkillQuery(
  value: string,
  caretPos: number
): { query: string; start: number; end: number } | null {
  const uptoCaret = value.slice(0, caretPos)
  const slash = uptoCaret.lastIndexOf('/')
  if (slash === -1) return null
  if (slash > 0 && !/\s/.test(uptoCaret[slash - 1])) return null
  const after = uptoCaret.slice(slash + 1)
  if (/\s/.test(after)) return null
  return { query: after, start: slash, end: caretPos }
}

export function computeAtFileQuery(
  value: string,
  caretPos: number
): { query: string; start: number; end: number } | null {
  const uptoCaret = value.slice(0, caretPos)
  const at = uptoCaret.lastIndexOf('@')
  if (at === -1) return null
  if (at > 0 && !/\s/.test(uptoCaret[at - 1])) return null
  const after = uptoCaret.slice(at + 1)
  if (/\s/.test(after)) return null
  return { query: after, start: at, end: caretPos }
}
