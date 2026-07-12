export function getFileIcon(fileName: string): string {
  const extension = fileName.toLowerCase().split('.').pop() || ''
  const icons: Record<string, string> = {
    md: 'vscode-icons:file-type-markdown',
    markdown: 'vscode-icons:file-type-markdown',
    js: 'vscode-icons:file-type-js',
    jsx: 'vscode-icons:file-type-reactjs',
    ts: 'vscode-icons:file-type-typescript',
    tsx: 'vscode-icons:file-type-reactts',
    py: 'vscode-icons:file-type-python',
    json: 'vscode-icons:file-type-json',
    yaml: 'vscode-icons:file-type-yaml',
    yml: 'vscode-icons:file-type-yaml',
    xml: 'vscode-icons:file-type-xml',
    html: 'vscode-icons:file-type-html',
    css: 'vscode-icons:file-type-css',
    csv: 'vscode-icons:file-type-excel',
    tsv: 'vscode-icons:file-type-excel',
    pdf: 'vscode-icons:file-type-pdf2',
    txt: 'vscode-icons:file-type-text',
    png: 'vscode-icons:file-type-image',
    jpg: 'vscode-icons:file-type-image',
    jpeg: 'vscode-icons:file-type-image',
    gif: 'vscode-icons:file-type-image',
    svg: 'vscode-icons:file-type-svg',
    webp: 'vscode-icons:file-type-image',
    pdb: 'vscode-icons:file-type-moleculer',
    cif: 'vscode-icons:file-type-moleculer',
    sdf: 'vscode-icons:file-type-moleculer',
    sh: 'vscode-icons:file-type-shell',
    bash: 'vscode-icons:file-type-shell',
    r: 'vscode-icons:file-type-r',
    sql: 'vscode-icons:file-type-sql',
    zip: 'vscode-icons:file-type-zip',
    tar: 'vscode-icons:file-type-zip',
    gz: 'vscode-icons:file-type-zip'
  }
  const lowerName = fileName.toLowerCase()
  if (lowerName === 'dockerfile') return 'vscode-icons:file-type-docker'
  if (lowerName === 'readme.md' || lowerName === 'readme') {
    return 'vscode-icons:file-type-readme'
  }
  if (lowerName.startsWith('.env')) return 'vscode-icons:file-type-dotenv'
  return icons[extension] || 'vscode-icons:default-file'
}
