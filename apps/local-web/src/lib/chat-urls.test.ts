import { describe, expect, it } from 'vitest'

import {
  findUrlRanges,
  splitTextWithUrls,
  trimUrlMatch
} from '@/lib/chat-urls'

describe('trimUrlMatch', () => {
  it('keeps trailing slash and strips sentence punctuation', () => {
    expect(trimUrlMatch('https://news.ycombinator.com/')).toBe(
      'https://news.ycombinator.com/'
    )
    expect(trimUrlMatch('https://example.com.')).toBe('https://example.com')
  })
})

describe('findUrlRanges / splitTextWithUrls', () => {
  it('splits text around http(s) URLs', () => {
    expect(
      splitTextWithUrls(
        'read this site https://news.ycombinator.com/\ngive me top 5'
      )
    ).toEqual([
      { type: 'text', text: 'read this site ' },
      {
        type: 'url',
        href: 'https://news.ycombinator.com/',
        text: 'https://news.ycombinator.com/'
      },
      { type: 'text', text: '\ngive me top 5' }
    ])
  })

  it('returns a single text segment when there is no URL', () => {
    expect(splitTextWithUrls('no links here')).toEqual([
      { type: 'text', text: 'no links here' }
    ])
  })

  it('finds ranges that cover the URL only', () => {
    const text = 'go https://example.com now'
    expect(findUrlRanges(text)).toEqual([{ start: 3, end: 22 }])
  })
})
