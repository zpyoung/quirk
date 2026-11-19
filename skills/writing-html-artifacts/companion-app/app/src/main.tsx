import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { applyStoredThemeMode } from './theme'
import './theme.css'
import './run/run.css'

const root = document.getElementById('root')
if (!root) throw new Error('Missing application root.')

applyStoredThemeMode()
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
