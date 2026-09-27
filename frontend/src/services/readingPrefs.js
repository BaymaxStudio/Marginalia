// 阅读设置通过 CSS 变量和 data-theme 生效；启动时和修改设置后都走这里。
// 本地缓存一份，避免深色用户在设置加载前先看到一闪而过的浅色页面。
const CACHE_KEY = 'marginalia:reading-prefs'
const THEMES = ['light', 'dark', 'system']

export const DEFAULT_PREFS = { font_size: 18, line_height: 1.8, theme: 'light' }

export function applyReadingPrefs({ font_size, line_height, theme } = {}) {
  const root = document.documentElement
  if (Number.isFinite(font_size) && font_size > 0) root.style.setProperty('--font-size', font_size + 'px')
  if (Number.isFinite(line_height) && line_height > 0) root.style.setProperty('--line-height', String(line_height))
  if (THEMES.includes(theme)) root.dataset.theme = theme
}

export function readCachedPrefs() {
  try {
    const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null')
    return cached && typeof cached === 'object' ? { ...DEFAULT_PREFS, ...cached } : DEFAULT_PREFS
  } catch {
    return DEFAULT_PREFS
  }
}

export function cachePrefs(prefs) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(prefs))
  } catch {
    // 隐私模式等情况下无法写入，只影响首屏主题，不影响使用
  }
}
