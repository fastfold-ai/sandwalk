import { Copy } from 'lucide-react'
import { useEffect, useState } from 'react'

import { useDesktopUpdate } from '@/hooks/useDesktopUpdate'
import { copyViaDesktop } from '@/lib/desktop'
import { fetchLastReleaseDate, formatReleaseAge } from '@/lib/release-date'

export function AboutUpdateWindow() {
  const update = useDesktopUpdate()
  const [copied, setCopied] = useState(false)
  const [released, setReleased] = useState<string | null>(null)

  useEffect(() => {
    document.documentElement.classList.add('sandwalk-about')
    void update.checkForUpdate({ quiet: true })
    return () => {
      document.documentElement.classList.remove('sandwalk-about')
    }
  }, [update.checkForUpdate])

  useEffect(() => {
    let cancelled = false
    void fetchLastReleaseDate().then(published => {
      if (cancelled || !published) return
      setReleased(formatReleaseAge(published))
    })
    return () => {
      cancelled = true
    }
  }, [])

  const versionLine = `Version ${update.currentVersion}`
  const copyVersionInfo = async () => {
    const lines = [
      'Sandwalk',
      versionLine,
      released || '',
      navigator.platform || ''
    ].filter(Boolean)
    const ok = await copyViaDesktop(lines.join('\n'))
    if (!ok) {
      try {
        await navigator.clipboard.writeText(lines.join('\n'))
      } catch {
        return
      }
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  const restartLabel = update.installing
    ? update.progress?.phase === 'download'
      ? 'Downloading…'
      : 'Restarting…'
    : 'Restart to Update'

  return (
    <div className="fixed inset-0 flex flex-col bg-[#2a2a2c] px-8 pt-14 pb-5 text-white">
      <style>{`
        html.sandwalk-about,
        html.sandwalk-about body,
        html.sandwalk-about #root {
          background: #2a2a2c !important;
          height: 100%;
        }
      `}</style>
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <img
          src="/dock-icons/light.png"
          alt=""
          className="size-16 rounded-2xl shadow-lg"
        />
        <h1 className="mt-4 text-[22px] font-medium tracking-tight">
          Sandwalk
        </h1>
        <p className="mt-1 text-[13px] text-white/70">{versionLine}</p>
        {released ? (
          <p className="mt-1 text-[12px] text-white/45">{released}</p>
        ) : null}
        <div className="mt-7 flex flex-wrap items-center justify-center gap-2">
          {update.available ? (
            <button
              type="button"
              className="rounded-md bg-[#3a3a3c] px-3.5 py-1.5 text-[13px] text-white hover:bg-[#48484a] disabled:opacity-60"
              disabled={update.installing}
              onClick={() => void update.installUpdate()}
            >
              {restartLabel}
            </button>
          ) : null}
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-md bg-[#3a3a3c] px-3.5 py-1.5 text-[13px] text-white hover:bg-[#48484a]"
            onClick={() => void copyVersionInfo()}
          >
            <Copy className="size-3.5 opacity-80" />
            {copied ? 'Copied' : 'Copy version info'}
          </button>
        </div>
        {update.error ? (
          <p className="mt-3 max-w-sm text-[12px] text-red-300">{update.error}</p>
        ) : null}
      </div>
      <p className="text-center text-[11px] text-white/40">
        © 2026 Fastfold AI Labs. All rights reserved.
      </p>
    </div>
  )
}
