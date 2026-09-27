import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listDocuments, uploadDocument, deleteDocument } from '../services/api'
import { usePrefs } from '../prefs/PrefsContext'
import AppHeader from '../components/AppHeader/AppHeader'
import Icon from '../components/Icon/Icon'
import './LibraryPage.css'

const MAX_SIZE = 50 * 1024 * 1024

export default function LibraryPage() {
  const navigate = useNavigate()
  const { hasApiKey } = usePrefs()
  const [docs, setDocs] = useState(null)
  const [uploading, setUploading] = useState('')
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef(null)
  const dragDepth = useRef(0)

  const load = async () => {
    try {
      const data = await listDocuments()
      setDocs(data.documents || [])
    } catch (e) {
      setDocs([])
      setError('书库加载失败：' + e.message)
    }
  }

  useEffect(() => { load() }, [])

  const upload = async (file) => {
    if (!file) return
    if (!/\.pdf$/i.test(file.name)) { setError('只支持 PDF 文件。'); return }
    if (file.size > MAX_SIZE) { setError('文件不能超过 50 MB。'); return }
    setUploading(file.name)
    setError('')
    try {
      const result = await uploadDocument(file)
      if (result.status === 'ready') navigate(`/reader/${result.document_id}`)
      else {
        setError('文档已上传，但还没有解析完成，请稍后刷新。')
        load()
      }
    } catch (e) {
      setError('导入失败：' + e.message)
    } finally {
      setUploading('')
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const remove = async (doc) => {
    if (!confirm(`删除《${doc.title}》？这本书的阅读进度和生词记录会一起删除，无法恢复。`)) return
    try {
      await deleteDocument(doc.id)
      load()
    } catch (e) {
      setError('删除失败：' + e.message)
    }
  }

  const dragProps = {
    onDragEnter: (e) => { e.preventDefault(); dragDepth.current += 1; setDragging(true) },
    onDragOver: (e) => e.preventDefault(),
    onDragLeave: () => { dragDepth.current -= 1; if (dragDepth.current <= 0) setDragging(false) },
    onDrop: (e) => {
      e.preventDefault()
      dragDepth.current = 0
      setDragging(false)
      upload(e.dataTransfer.files?.[0])
    },
  }

  const empty = docs && docs.length === 0

  return (
    <div className={`library${dragging ? ' is-dragging' : ''}`} {...dragProps}>
      <AppHeader />
      <main className="page">
        <input ref={fileRef} type="file" accept=".pdf,application/pdf" hidden
          onChange={(e) => upload(e.target.files?.[0])} />

        <div className="page-head">
          <div>
            <h1 className="page-title">书库</h1>
            <p className="page-sub">{docs ? `${docs.length} 本书` : '加载中…'}</p>
          </div>
          {!empty && (
            <div className="page-actions">
              <button type="button" className="btn btn-primary" onClick={() => fileRef.current?.click()} disabled={!!uploading}>
                <Icon name="upload" size={16} />导入 PDF
              </button>
            </div>
          )}
        </div>

        {hasApiKey === false && (
          <div className="notice library-notice">
            <Icon name="info" />
            <span>还没有配置 AI 服务。词典查词可以直接用，语境释义、段落评论和章节回顾需要先 <Link to="/settings">填写 API Key</Link>。</span>
          </div>
        )}
        {error && <div className="notice library-notice is-error" role="alert"><Icon name="info" /><span>{error}</span></div>}

        {uploading && (
          <div className="book is-pending">
            <div className="book-spine" />
            <div className="book-main">
              <div className="book-title">{uploading.replace(/\.pdf$/i, '')}</div>
              <div className="book-meta">正在解析章节结构，大文件需要一两分钟…</div>
            </div>
          </div>
        )}

        {empty && !uploading && (
          <button type="button" className="dropzone" onClick={() => fileRef.current?.click()}>
            <Icon name="upload" size={28} />
            <strong>导入第一本书</strong>
            <span>把 PDF 拖到这里，或点击选择文件</span>
            <small>支持文字版 PDF（非扫描件），最大 50 MB</small>
          </button>
        )}

        {docs && docs.length > 0 && (
          <ul className="books">
            {docs.map((d) => {
              const pct = Math.round(d.reading_progress_percent ?? 0)
              return (
                <li key={d.id} className="book">
                  <Link to={`/reader/${d.id}`} className="book-link" aria-label={`阅读《${d.title}》`} />
                  <div className="book-spine" aria-hidden="true">{d.title.trim().slice(0, 1).toUpperCase()}</div>
                  <div className="book-main">
                    <div className="book-title">{d.title}</div>
                    <div className="book-meta">
                      {d.total_chapters ? `${d.total_chapters} 章` : '章节未知'}
                      {d.upload_time && ` · 导入于 ${d.upload_time.slice(0, 10)}`}
                    </div>
                    <div className="book-progress">
                      <div className="book-bar"><span style={{ width: `${pct}%` }} /></div>
                      <span>{pct === 0 ? '未开始' : pct >= 100 ? '已读完' : `已读 ${pct}%`}</span>
                    </div>
                  </div>
                  <button type="button" className="icon-btn book-delete" aria-label={`删除《${d.title}》`}
                    onClick={() => remove(d)}>
                    <Icon name="trash" size={17} />
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </main>
      {dragging && <div className="drop-overlay" aria-hidden="true"><span>松开即可导入</span></div>}
    </div>
  )
}
