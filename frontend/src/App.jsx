import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import ReaderPage from './pages/ReaderPage'
import VocabularyPage from './pages/VocabularyPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/reader/:docId" element={<ReaderPage />} />
      <Route path="/vocabulary" element={<VocabularyPage />} />
      <Route path="/settings" element={<SettingsPage />} />
    </Routes>
  )
}
