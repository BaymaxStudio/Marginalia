import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import ReaderPage from './pages/ReaderPage'
import VocabularyPage from './pages/VocabularyPage'
import SettingsPage from './pages/SettingsPage'
import { getSettings } from './services/api'
import { applyReadingPrefs } from './services/readingPrefs'

export default function App() {
  useEffect(() => {
    getSettings()
      .then(applyReadingPrefs)
      .catch((e) => console.warn('读取阅读设置失败，使用默认字号和行高', e))
  }, [])

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/reader/:docId" element={<ReaderPage />} />
      <Route path="/vocabulary" element={<VocabularyPage />} />
      <Route path="/settings" element={<SettingsPage />} />
    </Routes>
  )
}
