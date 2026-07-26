import './index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App.tsx'
import { AppErrorBoundary } from './components/AppErrorBoundary.tsx'
import { Toaster } from './components/ui/sonner.tsx'
import { installBlockBrowserBackspace } from './lib/block-browser-backspace.ts'
import { isMacDesktopOverlay, platformOS } from './lib/desktop.ts'
import {
  applyLiquidGlass,
  applyPalette,
  applyTheme,
  getStoredLiquidGlass,
  getStoredPalette,
  getStoredTheme,
  watchSystemTheme
} from './lib/theme.ts'

applyTheme(getStoredTheme())
applyPalette(getStoredPalette())
watchSystemTheme()
installBlockBrowserBackspace()

document.documentElement.dataset.platform = platformOS()
if (isMacDesktopOverlay()) {
  document.documentElement.classList.add(
    'sandwalk-mac-overlay',
    'sandwalk-mac-glass',
    'sandwalk-mac-glass-active'
  )
  applyLiquidGlass(getStoredLiquidGlass())
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AppErrorBoundary>
        <App />
      </AppErrorBoundary>
      <Toaster richColors closeButton position="top-center" />
    </BrowserRouter>
  </StrictMode>
)
