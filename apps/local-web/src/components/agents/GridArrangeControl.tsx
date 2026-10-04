/** Equal-pane layouts for a group. `cols` is panes across. */
export function gridLayoutChoices(count: number): {
  label: string
  rows: number
  cols: number
}[] {
  if (count < 2) return []
  const raw = [
    { cols: count, label: 'One row' },
    { cols: 2, label: '2 across' },
    { cols: 3, label: '3 across' },
    { cols: 4, label: '4 across' },
    { cols: 1, label: 'One column' }
  ]
  const unique = raw.filter(
    (choice, index, all) => all.findIndex(item => item.cols === choice.cols) === index
  )
  return unique.map(choice => {
    const cols = Math.max(1, Math.min(choice.cols, count))
    return { label: choice.label, cols, rows: Math.ceil(count / cols) }
  })
}
