import { useEffect, useState } from 'react'

function SandwalkLogo() {
  return (
    <a
      className="sandwalk-brand"
      href="https://sandwalk.sh/"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Sandwalk"
    >
      <svg
        className="sandwalk-logo"
        viewBox="0 0 280 62"
        role="img"
        aria-hidden="true"
      >
        <g transform="translate(2 10) scale(0.085) translate(-72 -177)">
          <path d="M107 458c-19 0-35 16-35 35v70c0 19 16 35 35 35s35-16 35-35v-70c0-19-16-35-35-35z" />
          <path d="M213 283c-19 0-35 16-35 35v176c0 19 16 35 35 35s35-16 35-35V318c0-19-16-35-35-35z" />
          <path d="M318 177c-19 0-35 16-35 35v246c0 19 16 35 35 35s35-16 35-35V212c0-19-16-35-35-35z" />
          <path d="M422 265c-19 0-35 16-35 35v246c0 19 16 35 35 35s35-16 35-35V300c0-19-16-35-35-35z" />
          <path d="M529 353c-19 0-35 16-35 35v246c0 19 16 35 35 35s35-16 35-35V388c0-19-16-35-35-35z" />
          <path d="M634 318c-19 0-35 16-35 35v178c0 19 16 35 35 35s35-16 35-35V353c0-19-16-35-35-35z" />
          <path d="M739 248c-19 0-35 16-35 35v70c0 19 16 35 35 35s35-16 35-35v-70c0-19-16-35-35-35z" />
        </g>
        <text
          x="72"
          y="48"
          fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
          fontSize="52"
          letterSpacing="-2"
        >
          sandwalk
        </text>
      </svg>
    </a>
  )
}

export default function App() {
  const [dark, setDark] = useState(() => {
    try {
      const saved = localStorage.getItem('sandwalk-report-theme')
      if (saved) return saved === 'dark'
    } catch {
      // Sandboxed previews may not expose storage.
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    try {
      localStorage.setItem('sandwalk-report-theme', dark ? 'dark' : 'light')
    } catch {
      // Keep the in-memory theme when storage is unavailable.
    }
  }, [dark])

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="report-actions no-print">
        <button type="button" onClick={() => setDark(current => !current)}>
          ◐ Theme
        </button>
      </div>
      <div className="report-layout">
        <nav className="toc no-print" aria-label="Table of contents">
          <p>Contents</p>
          <a href="#overview">Overview</a>
          <a href="#findings">Findings</a>
          <a href="#method">Method</a>
        </nav>
        <main id="main">
          <header>
            <p className="report-meta">
              REPORT •{' '}
              <time className="report-date" dateTime="__SANDWALK_REPORT_DATE__">
                __SANDWALK_REPORT_DATE__
              </time>
            </p>
            <h1>Start with the finding that matters.</h1>
            <p className="lede">
              Replace this summary with a clear answer and build only the
              interaction that helps the reader understand the evidence.
            </p>
          </header>
          <section id="overview" aria-labelledby="overview-title">
            <h2 id="overview-title">Overview</h2>
            <p>
              This Vite/React starter produces a responsive static report with
              relative assets.
            </p>
          </section>
          <section id="findings" aria-labelledby="findings-title">
            <h2 id="findings-title">Findings</h2>
            <div className="card-grid">
              <article>
                <span>Primary result</span>
                <strong>42</strong>
                <small>Replace with sourced data.</small>
              </article>
              <article>
                <span>Confidence</span>
                <strong>High</strong>
                <small>Explain the evidence.</small>
              </article>
              <article>
                <span>Next action</span>
                <strong>Review</strong>
                <small>Give a concrete next step.</small>
              </article>
            </div>
          </section>
          <section id="method" aria-labelledby="method-title">
            <h2 id="method-title">Method</h2>
            <details>
              <summary>Assumptions and limitations</summary>
              <p>
                Document provenance, exclusions, uncertainty, and
                reproducibility details.
              </p>
            </details>
          </section>
          <footer>
            <span>Generated with</span>
            <SandwalkLogo />
          </footer>
        </main>
      </div>
    </>
  )
}
