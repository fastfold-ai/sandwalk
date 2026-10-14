import { describe, expect, it } from 'vitest'

import { backendUrlFromPage } from './backend-url'

describe('backendUrlFromPage', () => {
  it('uses the LAN host that served the dashboard', () => {
    expect(
      backendUrlFromPage({
        protocol: 'http:',
        hostname: '10.0.0.187',
        origin: 'http://10.0.0.187:8787',
        port: '8787'
      })
    ).toBe('http://10.0.0.187:8787')
  })

  it('keeps localhost and the Vite dev server on the local API', () => {
    expect(
      backendUrlFromPage({
        protocol: 'http:',
        hostname: '127.0.0.1',
        origin: 'http://127.0.0.1:8787',
        port: '8787'
      })
    ).toBeNull()
    expect(
      backendUrlFromPage({
        protocol: 'http:',
        hostname: '127.0.0.1',
        origin: 'http://127.0.0.1:1420',
        port: '1420'
      })
    ).toBeNull()
  })

  it('ignores the Tauri webview protocol', () => {
    expect(
      backendUrlFromPage({
        protocol: 'tauri:',
        hostname: 'localhost',
        origin: 'tauri://localhost',
        port: ''
      })
    ).toBeNull()
  })
})
