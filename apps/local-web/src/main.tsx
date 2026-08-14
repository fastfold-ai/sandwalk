import './index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, HashRouter } from 'react-router-dom'

import App from './App.tsx'
import { AppErrorBoundary } from './components/AppErrorBoundary.tsx'
import { Toaster } from './components/ui/sonner.tsx'
import { DesktopUpdateProvider } from './hooks/useDesktopUpdate.tsx'
import { installBlockBrowserBackspace } from './lib/block-browser-backspace.ts'
import { isMacDesktopOverlay, platformOS } from './lib/desktop.ts'
import { usesDesktopHashRouter } from './lib/desktop-spa-route.ts'
import {
  applyAccentColor,
  applyAppFont,
  applyCustomTheme,
  applyDockIcon,
  applyGlassMaterial,
  applyGlassTintStrength,
  applyLiquidGlass,
  applyPalette,
  applyTheme,
  applyUiFontSize,
  getStoredAccentColor,
  getStoredAppFont,
  getStoredCustomTheme,
  getStoredDockIcon,
  getStoredGlassMaterial,
  getStoredGlassTintStrength,
  getStoredLiquidGlass,
  getStoredPalette,
  getStoredTheme,
  getStoredUiFontSize,
  watchSystemTheme
} from './lib/theme.ts'

applyTheme(getStoredTheme())
applyPalette(getStoredPalette())
applyAccentColor(getStoredAccentColor())
applyCustomTheme(getStoredCustomTheme())
applyUiFontSize(getStoredUiFontSize())
applyAppFont(getStoredAppFont())
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
  applyGlassMaterial(getStoredGlassMaterial())
  applyGlassTintStrength(getStoredGlassTintStrength())
  applyDockIcon(getStoredDockIcon())
}

const Router = usesDesktopHashRouter() ? HashRouter : BrowserRouter

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Router>
      <AppErrorBoundary>
        <DesktopUpdateProvider>
          <App />
        </DesktopUpdateProvider>
      </AppErrorBoundary>
      <Toaster closeButton position="top-center" />
    </Router>
  </StrictMode>
)
