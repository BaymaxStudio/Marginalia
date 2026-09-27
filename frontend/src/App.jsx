import { Routes, Route } from 'react-router-dom'
import { PrefsProvider } from './prefs/PrefsContext'
import LibraryPage from './pages/LibraryPage'
import ReaderPage from './pages/ReaderPage'
import VocabularyPage from './pages/VocabularyPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <PrefsProvider>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/reader/:docId" element={<ReaderPage />} />
        <Route path="/vocabulary" element={<VocabularyPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </PrefsProvider>
  )
}
