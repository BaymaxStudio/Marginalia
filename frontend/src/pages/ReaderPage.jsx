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

  // Progress tracking
  const progressRef = useRef({})
  const saveTimerRef = useRef(null)
  const restoredRef = useRef(false)

  // Load structure + restore progress
  useEffect(() => {
    if (!docId) return
    setError('')
    getStructure(docId)
      .then(async (s) => {
        setStructure(s)
        const allChapters = s.chapters || []
        setChapters(allChapters)

        if (allChapters.length === 0) {
          setLoading(false)
          return
        }

        // Restore chapter status from backend
        try {
          const prog = await getProgress(docId)
          const savedStatus = prog.chapter_status || {}
          // 合并：已存储的章节状态 + 未读的新章节默认为 unread
          for (const ch of allChapters) {
            if (!savedStatus[ch.id]) savedStatus[ch.id] = 'unread'
          }
          progressRef.current = savedStatus
        } catch (_) {
          for (const ch of allChapters) progressRef.current[ch.id] = 'unread'
        }
        setChapterStatus({...progressRef.current})

        setActiveChapterId(targetChapterId)
        await loadChapterContent(targetChapterId, allChapters)
      })
      .catch((e) => {
        setError('加载文档失败: ' + e.message)
        setLoading(false)
      })
  }, [docId])

  const loadChapterContent = async (chId, chs = chapters) => {
    setLoading(true)
    setError('')
    try {
      const data = await getChapter(docId, chId)
      setChapterData(data)
    } catch (e) {
      setError('加载章节失败: ' + e.message)
    }
    setLoading(false)
  }

  // Restore scroll position after chapter renders
  useEffect(() => {
    if (!chapterData || restoredRef.current) return
    restoredRef.current = true

    getProgress(docId).then((prog) => {
      if (prog.last_paragraph_id) {
        // Small delay for DOM to render
        setTimeout(() => {
          const el = document.getElementById(prog.last_paragraph_id)
          if (el) el.scrollIntoView({ block: 'center' })
        }, 300)
      }
    }).catch(() => {})
  }, [chapterData?.chapter_id])

  // IntersectionObserver for auto-save
  useEffect(() => {
    if (!chapterData) return

    // 计算当前章最后一段的 ID
    let lastParaId = null
    for (const sec of (chapterData.sections || [])) {
      const paras = sec.paragraphs || []
      if (paras.length > 0) lastParaId = paras[paras.length - 1].id
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const pid = entry.target.id
            if (pid && pid.startsWith('para_')) {
              progressRef.current.last_paragraph_id = pid

              // 判断是否为当前章最后一段 → completed，否则 in_progress
              const newStatus = (pid === lastParaId) ? 'completed' : 'in_progress'

              if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
              saveTimerRef.current = setTimeout(() => {
                const updatedStatus = { ...progressRef.current }
                updatedStatus[activeChapterId] = newStatus
                progressRef.current = updatedStatus
                setChapterStatus({...updatedStatus})

                updateProgress(docId, {
                  last_paragraph_id: pid,
                  chapter_status: updatedStatus,
                }).catch(() => {})
              }, 2000)
            }
          }
        }
      },
      { threshold: 0.5 }
    )

    const paraElements = document.querySelectorAll('[id^="para_"]')
    paraElements.forEach((el) => observer.observe(el))

    return () => {
      observer.disconnect()
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [chapterData?.chapter_id, activeChapterId, docId])

  const switchChapter = (chId) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    // 仅保存当前阅读位置，不改变任何章节的完成状态（导航行为 ≠ 阅读行为）
    updateProgress(docId, {
      last_paragraph_id: progressRef.current.last_paragraph_id || '',
      chapter_status: progressRef.current,
    }).catch(() => {})

    setActiveChapterId(chId)
    setActiveComment(null)
    setWordCard(null)
    setShowChapterReview(false)
    restoredRef.current = false
    loadChapterContent(chId)
    window.scrollTo(0, 0)
  }

  const handleWordClick = useCallback((word, sentence, e, paragraphId) => {
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

  const renderParagraph = (text, paragraphId) => {
    if (!text) return null
    const tokens = text.match(/\b[\w'’-]+(?:-\n[\w'’-]+)?\b|[^\w\s]+|\s+/g) || [text]
    return (
      <span id={paragraphId} className="para-anchor" />
    )
    // Note: this is placeholder - real rendering is below
  }

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
          word={wordCard.word} sentence={wordCard.sentence}
          docId={wordCard.docId} paragraphId={wordCard.paragraphId}
          x={wordCard.x} y={wordCard.y}
          onClose={() => setWordCard(null)}
        />
      )}
    </div>
  )
}
