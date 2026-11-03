import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import "./lib/mini/press"
import App from "./App.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>
)
