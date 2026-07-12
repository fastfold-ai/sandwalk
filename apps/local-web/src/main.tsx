import './index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App.tsx'
import { Toaster } from './components/ui/sonner.tsx'
import { applyTheme, getStoredTheme } from './lib/theme.ts'

applyTheme(getStoredTheme())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
      <Toaster richColors closeButton position="top-center" />
    </BrowserRouter>
  </StrictMode>
)
