// 阅读设置通过 CSS 变量生效；启动时和保存设置后都走这里。
export function applyReadingPrefs({ font_size, line_height } = {}) {
  const root = document.documentElement.style
  if (Number.isFinite(font_size) && font_size > 0) root.setProperty('--font-size', font_size + 'px')
  if (Number.isFinite(line_height) && line_height > 0) root.setProperty('--line-height', String(line_height))
}
