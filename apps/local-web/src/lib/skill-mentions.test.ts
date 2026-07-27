import { describe, expect, it } from 'vitest'

import { splitTextWithSkillMentions } from '@/lib/skill-mentions'

describe('splitTextWithSkillMentions', () => {
  it('parses slash mentions and composer tokens', () => {
    expect(splitTextWithSkillMentions('Installed /lab-notes today')).toEqual([
      { type: 'text', text: 'Installed ' },
      { type: 'skill', name: 'lab-notes' },
      { type: 'text', text: ' today' }
    ])
    expect(splitTextWithSkillMentions('Open ⟦/:fold⟧ please')).toEqual([
      { type: 'text', text: 'Open ' },
      { type: 'skill', name: 'fold' },
      { type: 'text', text: ' please' }
    ])
  })

  it('does not treat filesystem paths as skills', () => {
    const text = 'see /Users/juliocesar/.sandwalk/skills/lab-notes'
    const parts = splitTextWithSkillMentions(text)
    expect(parts).toEqual([{ type: 'text', text }])
  })

  it('still matches a skill after punctuation', () => {
    expect(splitTextWithSkillMentions('Installed /lab-notes.')).toEqual([
      { type: 'text', text: 'Installed ' },
      { type: 'skill', name: 'lab-notes' },
      { type: 'text', text: '.' }
    ])
  })

  it('does not treat URL path segments as skills', () => {
    const text = 'read https://news.ycombinator.com/ then /lab-notes'
    expect(splitTextWithSkillMentions(text)).toEqual([
      { type: 'text', text: 'read https://news.ycombinator.com/ then ' },
      { type: 'skill', name: 'lab-notes' }
    ])
  })
})
