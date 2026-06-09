import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { listDocuments, uploadDocument, deleteDocument, getSettings } from '../services/api'
import './HomePage.css'

export default function HomePage() {
  const [docs, setDocs] = useState([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [showBanner, setShowBanner] = useState(false)
  const fileRef = useRef(null)
  const navigate = useNavigate()

  const load = async () => {
    try {
      const data = await listDocuments()
      setDocs(data.documents || [])
    } catch (e) { setError(e.message) }
  }

  const checkApiKey = async () => {
    try {
      const s = await getSettings()
      setShowBanner(!s.has_api_key)
    } catch (_) {}
  }

  useEffect(() => { load(); checkApiKey() }, [])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.endsWith('.pdf')) { setError('仅支持 PDF 文件'); return }
    if (file.size > 50 * 1024 * 1024) { setError('文件不能超过 50MB'); return }

    setUploading(true)
    setError('')
    try {
      const result = await uploadDocument(file)
      if (result.status === 'ready') {
        await load()
        navigate(`/reader/${result.document_id}`)
      }
    } catch (e) { setError(e.message) }
    finally { setUploading(false) }
  }

  const handleDelete = async (id, title) => {
    if (!confirm(`确定删除「${title}」？`)) return
    try { await deleteDocument(id); load() }
    catch (e) { setError(e.message) }
  }

  return (
    <div className="home">
      <header className="home-header">
        <h1>Marginalia</h1>
        <p className="subtitle">AI 辅助学术阅读器</p>
        <nav>
          <a href="/vocabulary">生词本</a>
          <a href="/settings">设置</a>
        </nav>
      </header>

      {showBanner && (
        <div className="welcome-banner">
          <span className="welcome-banner-text">
            欢迎使用 Marginalia！开始之前，请先配置 AI 服务以启用智能功能。
          </span>
          <a href="/settings" className="welcome-banner-link">前往设置 →</a>
          <button className="welcome-banner-close" onClick={() => setShowBanner(false)}
            title="关闭" aria-label="关闭">x</button>
        </div>
      )}

      {error && <div className="error-msg">{error}</div>}

      <section className="upload-area" onClick={() => fileRef.current?.click()}>
        <input ref={fileRef} type="file" accept=".pdf" onChange={handleUpload} hidden />
        <div className="upload-icon">+</div>
        <p>{uploading ? '正在解析文档...' : '点击上传 PDF 文档'}</p>
        <p className="upload-hint">支持数字版 PDF（非扫描版），最大 50MB</p>
      </section>

      <section className="doc-list">
        <h2>我的文档</h2>
        {docs.length === 0 && <p className="empty">暂无文档，上传一篇开始阅读吧</p>}
        {docs.map((d) => (
          <div key={d.id} className="doc-card" onClick={() => navigate(`/reader/${d.id}`)}>
            <div className="doc-info">
              <h3>{d.title}</h3>
              <p className="doc-meta">{d.total_chapters || '?'} 章 · 进度 {d.reading_progress_percent ?? 0}%</p>
              <p className="doc-date">{d.upload_time?.slice(0, 10)}</p>
            </div>
            <button className="btn-delete" onClick={(e) => { e.stopPropagation(); handleDelete(d.id, d.title) }}>
              删除
            </button>
          </div>
        ))}
      </section>
    </div>
  )
}
