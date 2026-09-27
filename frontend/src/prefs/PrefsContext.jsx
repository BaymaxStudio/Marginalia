import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { getSettings, updateSettings } from '../services/api'
import { applyReadingPrefs, cachePrefs, readCachedPrefs } from '../services/readingPrefs'

const PrefsContext = createContext(null)

// 阅读偏好（字号、行高、主题）改动即时生效并自动保存；AI 配置状态供书库提示使用。
export function PrefsProvider({ children }) {
  const [prefs, setPrefs] = useState(readCachedPrefs)
  const [hasApiKey, setHasApiKey] = useState(null)
  const [saveError, setSaveError] = useState('')
  const pendingRef = useRef({})
  const timerRef = useRef(null)

  const refresh = useCallback(async () => {
    try {
      const s = await getSettings()
      setPrefs({ font_size: s.font_size, line_height: s.line_height, theme: s.theme })
      setHasApiKey(Boolean(s.has_api_key))
    } catch (e) {
      console.warn('读取设置失败，使用本地缓存的阅读设置', e)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    applyReadingPrefs(prefs)
    cachePrefs(prefs)
  }, [prefs])

  const updatePrefs = useCallback((patch) => {
    setPrefs((p) => ({ ...p, ...patch }))
    pendingRef.current = { ...pendingRef.current, ...patch }
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      const body = pendingRef.current
      pendingRef.current = {}
      updateSettings(body)
        .then(() => setSaveError(''))
        .catch((e) => setSaveError('阅读设置未能保存：' + e.message))
    }, 400)
  }, [])

  useEffect(() => () => clearTimeout(timerRef.current), [])

  return (
    <PrefsContext.Provider value={{ prefs, updatePrefs, saveError, hasApiKey, refresh }}>
      {children}
    </PrefsContext.Provider>
  )
}

export function usePrefs() {
  return useContext(PrefsContext)
}
