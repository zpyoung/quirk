import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { applyStoredThemeMode } from './theme'
import './theme.css'

const queryClient = new QueryClient()
const root = document.getElementById('root')
if (!root) throw new Error('Missing application root.')

applyStoredThemeMode()
createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
