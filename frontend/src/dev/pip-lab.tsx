import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/patrick-hand/400.css'
import '@fontsource/gochi-hand/400.css'
import '@fontsource/space-mono/400.css'
import '../index.css'
import { PipLab } from './PipLab'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PipLab />
  </StrictMode>,
)
