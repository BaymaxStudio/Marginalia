import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { applyReadingPrefs, readCachedPrefs } from './services/readingPrefs'
import './styles/tokens.css'
import './styles/base.css'

// 首帧前先套用缓存的主题和字号，避免闪烁
applyReadingPrefs(readCachedPrefs())

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
