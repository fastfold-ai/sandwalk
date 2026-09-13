import { describe, expect, it } from 'vitest'

import { benchExportFilename } from './bench-export-name'

describe('benchExportFilename', () => {
  it('uses the short model id and suite', () => {
    expect(
      benchExportFilename(
        'moonshotai/kimi-k3',
        'bixbench-verified-50'
      )
    ).toBe('kimi-k3_bixbench-verified-50.json')
  })

  it('strips unsafe characters', () => {
    expect(benchExportFilename('org/foo:bar', 'suite/name')).toBe(
      'foo-bar_suite-name.json'
    )
  })
})
