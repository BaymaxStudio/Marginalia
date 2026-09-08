import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getStructure, getChapter, getProgress, updateProgress } from '../services/api'
import WordCard from '../components/WordCard/WordCard'
import CommentPanel from '../components/CommentPanel/CommentPanel'
import ChapterReview from '../components/ChapterReview/ChapterReview'
import './ReaderPage.css'

export default function ReaderPage() {
  const { docId } = useParams()
  const navigate = useNavigate()

  const [structure, setStructure] = useState(null)
  const [chapters, setChapters] = useState([])
  const [activeChapterId, setActiveChapterId] = useState(null)
  const [chapterData, setChapterData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [wordCard, setWordCard] = useState(null)
  const [activeComment, setActiveComment] = useState(null)
  const [showChapterReview, setShowChapterReview] = useState(false)
  const [chapterStatus, setChapterStatus] = useState({})

  const progressRef = useRef({})
  const restoreParagraphRef = useRef(null)
  const chapterRequestRef = useRef(0)

  // 章节响应可能乱序返回，只接受最近一次导航的结果。
  const loadChapterContent = async (chId) => {
    const requestId = ++chapterRequestRef.current
    setLoading(true)
    setChapterData(null)
    setError('')
    try {
      const data = await getChapter(docId, chId)
      if (requestId === chapterRequestRef.current) setChapterData(data)
    } catch (e) {
      if (requestId === chapterRequestRef.current) setError('加载章节失败: ' + e.message)
    } finally {
      if (requestId === chapterRequestRef.current) setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    setStructure(null)
    setChapters([])
    setChapterData(null)
    setActiveChapterId(null)
    setWordCard(null)
    setActiveComment(null)
    setShowChapterReview(false)
    progressRef.current = {}
    restoreParagraphRef.current = null
    setChapterStatus({})

    async function initialize() {
      try {
        const s = await getStructure(docId)
        if (cancelled) return
        setStructure(s)
        const allChapters = s.chapters || []
        setChapters(allChapters)
        if (!allChapters.length) {
          setLoading(false)
          return
        }
        const prog = await getProgress(docId).catch(() => ({}))
        if (cancelled) return
        // 只保留章节状态，兼容旧版本混入 last_paragraph_id 的记录。
        const statuses = Object.fromEntries(allChapters.map(ch => [
          ch.id, ['unread', 'in_progress', 'completed'].includes(prog.chapter_status?.[ch.id])
            ? prog.chapter_status[ch.id] : 'unread',
        ]))
        progressRef.current = statuses
        setChapterStatus(statuses)
        const savedParagraph = prog.last_paragraph_id || ''
        const chapterNumber = /^para_(\d+)_/.exec(savedParagraph)?.[1]
        const targetChapterId = allChapters.find(ch => ch.id === `ch_${chapterNumber}`)?.id
          || allChapters[0].id
        restoreParagraphRef.current = savedParagraph
        setActiveChapterId(targetChapterId)
        await loadChapterContent(targetChapterId)
      } catch (e) {
        if (!cancelled) {
          setError('加载文档失败: ' + e.message)
          setLoading(false)
        }
      }
    }
    initialize()
    return () => {
      cancelled = true
      chapterRequestRef.current += 1
    }
  }, [docId])

  useEffect(() => {
    if (!chapterData) return
    const paragraphId = restoreParagraphRef.current
    restoreParagraphRef.current = null
    if (paragraphId) document.getElementById(paragraphId)?.scrollIntoView({ block: 'center' })
  }, [chapterData])

  useEffect(() => {
    if (!chapterData || chapterData.chapter_id !== activeChapterId) return
    const paragraphs = (chapterData.sections || []).flatMap(sec => sec.paragraphs || [])
    const lastParaId = paragraphs.at(-1)?.id
    let saveTimer = null
    let pendingProgress = null
    const save = () => {
      if (!pendingProgress) return
      const snapshot = pendingProgress
      pendingProgress = null
      updateProgress(docId, snapshot).catch(() => {})
    }
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        const pid = entry.target.id
        // 已读章节回看前文时仍保持已读；离开页面前保存待写入的进度。
        const status = pid === lastParaId || progressRef.current[activeChapterId] === 'completed'
          ? 'completed' : 'in_progress'
        const updatedStatus = { ...progressRef.current, [activeChapterId]: status }
        progressRef.current = updatedStatus
        setChapterStatus(updatedStatus)
        pendingProgress = { last_paragraph_id: pid, chapter_status: updatedStatus }
        clearTimeout(saveTimer)
        saveTimer = setTimeout(save, 2000)
      }
    }, { threshold: 0.5 })
    for (const para of paragraphs) {
      const el = document.getElementById(para.id)
      if (el) observer.observe(el)
    }
    return () => {
      observer.disconnect()
      clearTimeout(saveTimer)
      save()
    }
  }, [chapterData, activeChapterId, docId])

  const switchChapter = (chId) => {
    if (chId === activeChapterId && chapterData) return
    restoreParagraphRef.current = null
    setActiveChapterId(chId)
    setActiveComment(null)
    setWordCard(null)
    setShowChapterReview(false)
    loadChapterContent(chId)
    window.scrollTo(0, 0)
  }

  const handleWordClick = useCallback((word, sentence, e, paragraphId) => {
    e.stopPropagation()
    const rect = e.target.getBoundingClientRect()
    setWordCard({
      word, sentence,
      x: rect.left + rect.width / 2,
      y: rect.bottom + 8,
      paragraphId,
      docId,
    })
  }, [docId])

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') setWordCard(null) }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="reader-layout">
      <aside className="reader-sidebar">
        <button className="btn-back" onClick={() => navigate('/')}>← 文库</button>
        <h2 className="sidebar-title">{structure?.title || '加载中...'}</h2>
        <nav className="toc">
          {chapters.map((ch) => {
            const status = chapterStatus[ch.id] || 'unread'
            const statusIcon = status === 'completed' ? '✓' : status === 'in_progress' ? '●' : '○'
            const statusColor = status === 'completed' ? '#8b9e6b' : status === 'in_progress' ? '#d4a853' : '#c8c0b0'
            return (
            <div key={ch.id}>
              <button
                className={`toc-chapter ${ch.id === activeChapterId ? 'active' : ''}`}
                onClick={() => switchChapter(ch.id)}>
                <span className="toc-status" style={{color: statusColor}}>{statusIcon}</span>
                {ch.title.length > 40 ? ch.title.slice(0, 40) + '...' : ch.title}
              </button>
              {ch.id === activeChapterId && ch.sections?.map((sec) => (
                <button key={sec.id} className="toc-section"
                  onClick={() => {
                    const el = document.getElementById(sec.id)
                    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                  }}>
                  {sec.title || '(未命名)'}
                </button>
              ))}
            </div>
            )
          })}
        </nav>
      </aside>

      <main className="reader-main" onClick={() => wordCard && setWordCard(null)}>
        {error && <div className="error-banner">{error}</div>}
        {loading && <div className="loading">加载中...</div>}

        {chapterData && !loading && (
          <article className="chapter-content">
            <h1 className="chapter-title">{chapterData.title}</h1>

            {chapterData.sections?.map((sec) => (
              <section key={sec.id} id={sec.id} className="section-block">
                {sec.title && <h2 className="section-title">{sec.title}</h2>}

                {sec.paragraphs?.map((para) => (
                  <div key={para.id} className="paragraph-wrapper" id={para.id}>
                    <p className="para-text">
                      {(para.text.match(/\b[\w'’-]+(?:-\n[\w'’-]+)?\b|[^\w\s]+|\s+/g) || [para.text]).map((token, i) => {
                        if (/^\s+$/.test(token)) return <span key={i}>{token}</span>
                        if (!/^[\w'’-]/.test(token)) return <span key={i}>{token}</span>
                        return (
                          <span key={i} className="word-clickable"
                            onClick={(e) => handleWordClick(token.replace(/\n/g, ''), para.text, e, para.id)}
                            title="点击查词">
                            {token}
                          </span>
                        )
                      })}
                    </p>
                    <button className="btn-comment"
                      onClick={(e) => {
                        e.stopPropagation()
                        setActiveComment(activeComment === para.id ? null : para.id)
                      }}>
                      💬 评论
                    </button>

                    {activeComment === para.id && (
                      <CommentPanel docId={docId} paragraphId={para.id}
                        onClose={() => setActiveComment(null)} />
                    )}

                    {chapterData.images
                      ?.filter((img) => img.after_paragraph === para.id)
                      .map((img) => (
                        <figure key={img.id} className="embedded-figure">
                          <img src={img.url} alt={img.caption || 'Figure'} loading="lazy" />
                          {img.caption && <figcaption>{img.caption}</figcaption>}
                        </figure>
                      ))}
                  </div>
                ))}
              </section>
            ))}

            <div className="chapter-end">
              <button className="btn-review"
                onClick={() => setShowChapterReview(!showChapterReview)}>
                📖 {showChapterReview ? '收起回顾' : '章节回顾'}
              </button>
              {showChapterReview && (
                <ChapterReview docId={docId} chapterId={activeChapterId} />
              )}
            </div>
          </article>
        )}

        {!loading && !chapterData && !error && (
          <div className="empty-state">该文档没有可显示的内容</div>
        )}
      </main>

      {wordCard && (
        <WordCard
          key={`${wordCard.docId}:${wordCard.paragraphId}:${wordCard.word}`}
          word={wordCard.word} sentence={wordCard.sentence}
          docId={wordCard.docId} paragraphId={wordCard.paragraphId}
          x={wordCard.x} y={wordCard.y}
          onClose={() => setWordCard(null)}
        />
      )}
    </div>
  )
}
