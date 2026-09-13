/** Readable download name: `kimi-k3_bixbench-verified-50.json`. */
export function benchExportFilename(
  modelId?: string | null,
  benchmark?: string | null
): string {
  const model = String(modelId || 'model').split('/').pop() || 'model'
  const bench = String(benchmark || 'bench')
  return `${safeExportPart(model)}_${safeExportPart(bench)}.json`
}

function safeExportPart(value: string): string {
  return (
    value
      .replace(/[^\w.+-]+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-+|-+$/g, '') || 'file'
  )
}
