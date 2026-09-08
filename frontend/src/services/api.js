const BASE_URL = '/api'

async function request(url, options = {}) {
  const res = await fetch(`${BASE_URL}${url}`, {
    ...options,
    headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ---- 文档管理 ----

export const uploadDocument = (file) => {
  const form = new FormData()
  form.append('file', file)
  return request('/documents/upload', { method: 'POST', body: form })
}

export const listDocuments = () => request('/documents')

export const getStructure = (docId) => request(`/documents/${docId}/structure`)

export const getChapter = (docId, chapterId) =>
  request(`/documents/${docId}/chapters/${chapterId}`)

export const deleteDocument = (docId) =>
  request(`/documents/${docId}`, { method: 'DELETE' })

// ---- 词义查询 ----

export const dictionaryLookup = (word, options = {}) => request(`/dictionary/${encodeURIComponent(word)}`, options)

export const aiLookup = (body, options = {}) => request('/lookup/ai', {
  ...options,
  method: 'POST',
  body: JSON.stringify(body),
})

// ---- 评论 ----

export const paragraphCommentary = (body) => request('/commentary/paragraph', {
  method: 'POST',
  body: JSON.stringify(body),
})

export const chapterReview = (body) => request('/commentary/chapter', {
  method: 'POST',
  body: JSON.stringify(body),
})

// ---- 生词本 ----

export const listVocabulary = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return request(`/vocabulary${qs ? '?' + qs : ''}`)
}

// ---- 阅读进度 ----

export const getProgress = (docId) => request(`/progress/${docId}`)

export const updateProgress = (docId, body) => request(`/progress/${docId}`, {
  method: 'PUT',
  body: JSON.stringify(body),
})

// ---- 设置 ----

export const getSettings = () => request('/settings')

export const updateSettings = (body) => request('/settings', {
  method: 'PUT',
  body: JSON.stringify(body),
})
