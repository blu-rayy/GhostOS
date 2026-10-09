import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
// Fonts are bundled with the app (OFL-1.1, @fontsource) so the UI works offline.
import '@fontsource/patrick-hand/400.css'
import '@fontsource/gochi-hand/400.css'
import '@fontsource/space-mono/400.css'
import '@fontsource/space-mono/700.css'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
