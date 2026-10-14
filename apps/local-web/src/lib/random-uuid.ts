/**
 * `crypto.randomUUID` exists only in a secure context. A phone opening the
 * dashboard at `http://mac.local:8787` has `crypto` but not `randomUUID`,
 * and the call throws. `getRandomValues` still works there.
 *
 * Capture the native function at load. The polyfill installs this module's
 * function onto `crypto`, so looking it up again would recurse.
 */
const nativeRandomUUID = globalThis.crypto?.randomUUID?.bind(globalThis.crypto)

function uuidFromBytes(): string {
  const bytes = new Uint8Array(16)
  const cryptoObj = globalThis.crypto
  if (cryptoObj && typeof cryptoObj.getRandomValues === 'function') {
    cryptoObj.getRandomValues(bytes)
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256)
    }
  }
  bytes[6] = (bytes[6]! & 0x0f) | 0x40
  bytes[8] = (bytes[8]! & 0x3f) | 0x80
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function randomUUID(): string {
  if (typeof nativeRandomUUID === 'function') return nativeRandomUUID()
  return uuidFromBytes()
}

export function installRandomUUIDPolyfill(): void {
  const cryptoObj = globalThis.crypto
  if (!cryptoObj || typeof cryptoObj.randomUUID === 'function') return
  try {
    Object.defineProperty(cryptoObj, 'randomUUID', {
      configurable: true,
      writable: true,
      value: randomUUID
    })
  } catch {
    // The property can be a non-configurable getter. Direct callers use randomUUID().
  }
}

installRandomUUIDPolyfill()
