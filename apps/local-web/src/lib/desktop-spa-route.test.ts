import { describe, expect, it } from 'vitest'

import { desktopReloadTarget, desktopSpaRoute } from '@/lib/desktop-spa-route'

describe('desktopSpaRoute', () => {
  it('reads the hash path used by the packaged WebView', () => {
    expect(
      desktopSpaRoute({
        pathname: '/index.html',
        search: '',
        hash: '#/dashboard/models'
      })
    ).toBe('/dashboard/models')
  })

  it('keeps hash query string for Open Recent', () => {
    expect(
      desktopSpaRoute({
        pathname: '/index.html',
        search: '',
        hash: '#/dashboard/general?checkUpdates=1'
      })
    ).toBe('/dashboard/general?checkUpdates=1')
  })

  it('treats a bare index document as home', () => {
    expect(
      desktopSpaRoute({ pathname: '/index.html', search: '', hash: '' })
    ).toBe('/')
  })

  it('falls back to history URLs from older builds', () => {
    expect(
      desktopSpaRoute({
        pathname: '/dashboard/models',
        search: '',
        hash: ''
      })
    ).toBe('/dashboard/models')
  })
})

describe('desktopReloadTarget', () => {
  it('reloads when the document is already index.html', () => {
    expect(
      desktopReloadTarget({
        pathname: '/index.html',
        search: '',
        hash: '#/dashboard/models'
      })
    ).toBe('reload')
  })

  it('rewrites a history SPA URL onto index.html plus hash', () => {
    expect(
      desktopReloadTarget({
        pathname: '/dashboard/models',
        search: '',
        hash: ''
      })
    ).toEqual({ replace: '/index.html#/dashboard/models' })
  })

  it('keeps search params on the rewritten hash', () => {
    expect(
      desktopReloadTarget({
        pathname: '/dashboard/general',
        search: '?checkUpdates=1',
        hash: ''
      })
    ).toEqual({ replace: '/index.html#/dashboard/general?checkUpdates=1' })
  })
})
