#!/usr/bin/env node
/* global process, console */
/**
 * Compare two bench reports written by e2e/bench specs.
 *
 *   pnpm e2e:compare e2e/results/grid-baseline.json e2e/results/grid-latest.json
 *
 * Prints per-measurement deltas and exits 1 when a tracked metric regressed
 * by more than the threshold (default 25%, `--threshold=0.1`).
 */
import { readFileSync } from 'node:fs'

const args = process.argv.slice(2).filter(a => !a.startsWith('--'))
const thresholdArg = process.argv.find(a => a.startsWith('--threshold='))
const threshold = thresholdArg ? Number(thresholdArg.split('=')[1]) : 0.25
if (args.length !== 2) {
  console.error('usage: compare.mjs <baseline.json> <candidate.json> [--threshold=0.25]')
  process.exit(2)
}
const [base, cand] = args.map(p => JSON.parse(readFileSync(p, 'utf8')))

/** Lower is better for these; counters starting with these prefixes too. */
const LOWER_IS_BETTER = ['durationMs', 'longTasks', 'longTaskMs']
const COUNTER_PREFIXES = ['terminal.', 'render.']
/** Informational counters: shown, never flagged (more filtering is good). */
const NEUTRAL_COUNTERS = new Set(['terminal.scrollIgnored', 'terminal.inputQueued', 'terminal.wsOpen'])
/** Minimum absolute change before a % delta counts (sub-second timings are noisy). */
const MIN_ABS_DELTA = { durationMs: 250, longTaskMs: 200, longTasks: 3, default: 2 }

const byName = list => Object.fromEntries(list.map(m => [m.name, m]))
const b = byName(base.measurements)
const c = byName(cand.measurements)

let regressions = 0
const pct = (from, to) => (from === 0 ? (to === 0 ? 0 : Infinity) : (to - from) / from)
const fmt = v => (v === Infinity ? '+inf' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(0)}%`)

console.log(`baseline  ${base.gitSha ?? '?'}  ${base.createdAt}  ${JSON.stringify(base.config)}`)
console.log(`candidate ${cand.gitSha ?? '?'}  ${cand.createdAt}  ${JSON.stringify(cand.config)}\n`)

for (const name of Object.keys({ ...b, ...c })) {
  const mb = b[name]
  const mc = c[name]
  if (!mb || !mc) {
    console.log(`${name}: only in ${mb ? 'baseline' : 'candidate'}`)
    continue
  }
  console.log(name)
  const rows = []
  for (const key of LOWER_IS_BETTER) rows.push([key, mb[key], mc[key], true])
  rows.push(['fps', mb.fps, mc.fps, false])
  const counterKeys = new Set([...Object.keys(mb.counters), ...Object.keys(mc.counters)])
  for (const key of [...counterKeys].sort()) {
    if (!COUNTER_PREFIXES.some(p => key.startsWith(p))) continue
    rows.push([key, mb.counters[key] ?? 0, mc.counters[key] ?? 0, NEUTRAL_COUNTERS.has(key) ? null : true])
  }
  for (const [key, from, to, lowerBetter] of rows) {
    const delta = pct(from, to)
    const minAbs = MIN_ABS_DELTA[key] ?? MIN_ABS_DELTA.default
    const bad =
      lowerBetter === null
        ? false
        : lowerBetter
          ? delta > threshold && to - from >= minAbs
          : delta < -threshold && from - to >= minAbs
    if (bad) regressions += 1
    console.log(`  ${key.padEnd(28)} ${String(from).padStart(8)} → ${String(to).padStart(8)}  ${fmt(delta).padStart(7)} ${bad ? ' REGRESSION' : ''}`)
  }
}

if (regressions > 0) {
  console.log(`\n${regressions} metric(s) regressed beyond ${threshold * 100}%`)
  process.exit(1)
}
console.log('\nno regressions beyond threshold')
