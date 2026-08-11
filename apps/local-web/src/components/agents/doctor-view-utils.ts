import type { DoctorCheckResult, DoctorReport } from '@sandwalk/agent-ui-core'
import {
  AlertTriangle,
  CheckCircle2,
  XCircle
} from 'lucide-react'

export const CATEGORY_ORDER = [
  'runtime',
  'tooling',
  'llm',
  'environment',
  'skills',
  'tools',
  'paths',
  'data',
  'network',
  'config',
  'policy',
  'mcp',
  'general'
]

export const SCAN_PHASES = [
  'Checking runtime & tooling…',
  'Validating LLM and API keys…',
  'Scanning skills and tools…',
  'Probing MCP servers…',
  'Finishing diagnostics…'
]

export function statusIcon(status: DoctorCheckResult['status']) {
  if (status === 'ok') return CheckCircle2
  if (status === 'warn') return AlertTriangle
  return XCircle
}

export function collectUiDiagnostics(report: DoctorReport | null) {
  return {
    generatedAt: new Date().toISOString(),
    href: window.location.href,
    userAgent: navigator.userAgent,
    language: navigator.language,
    online: navigator.onLine,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
      devicePixelRatio: window.devicePixelRatio
    },
    localStorageKeys: Object.keys(window.localStorage || {}),
    doctorSummary: report?.summary ?? null,
    doctorOk: report?.ok ?? null
  }
}

export function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function groupDoctorChecks(report: DoctorReport | null) {
  const checks = report?.checks || []
  const map = new Map<string, DoctorCheckResult[]>()
  for (const check of checks) {
    const key = check.category || 'general'
    const list = map.get(key) || []
    list.push(check)
    map.set(key, list)
  }
  return [...map.entries()].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a[0])
    const bi = CATEGORY_ORDER.indexOf(b[0])
    const av = ai === -1 ? CATEGORY_ORDER.length : ai
    const bv = bi === -1 ? CATEGORY_ORDER.length : bi
    if (av !== bv) return av - bv
    return a[0].localeCompare(b[0])
  })
}
