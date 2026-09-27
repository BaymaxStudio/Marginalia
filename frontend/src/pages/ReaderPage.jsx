import { memo, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { getStructure, getChapter, getProgress, updateProgress } from '../services/api'
import { useMediaQuery } from '../hooks/useMediaQuery'
import Icon from '../components/Icon/Icon'
import Toc from '../components/Toc/Toc'
import WordGloss from '../components/Notes/WordGloss'
import ParagraphComments from '../components/Notes/ParagraphComments'
import ChapterReview from '../components/ChapterReview/ChapterReview'
import BottomSheet from '../components/BottomSheet/BottomSheet'
import ReadingPrefsPanel from '../components/ReadingPrefs/ReadingPrefsPanel'
import './ReaderPage.css'

const WIDE_QUERY = '(min-width: 1024px)'
const RAIL_QUERY = '(min-width: 1360px)'
const TOKEN_RE = /\b[\w'’-]+(?:-\n[\w'’-]+)?\b|[^\w\s]+|\s+/g

// 段落正文：单词可点；只有当前查询的词高亮。memo 避免每次查词都重排整章。
const ParagraphText = memo(function ParagraphText({ text, activeIndex }) {
  const tokens = text.match(TOKEN_RE) || [text]
  return tokens.map((token, i) => (/^[A-Za-z]/.test(token)
    ? <span key={i} className={`w${i === activeIndex ? ' is-active' : ''}`} data-i={i}>{token}</span>
    : token))
})

function chapterIdFromParagraph(paragraphId, chapters) {
  const n = /^para_(\d+)_/.exec(paragraphId || '')?.[1]
  return chapters.find((ch) => ch.id === `ch_${n}`)?.id
}

export default function ReaderPage() {
  const { docId } = useParams()
  const [searchParams] = useSearchParams()
  const wide = useMediaQuery(WIDE_QUERY)
  const railPinned = useMediaQuery(RAIL_QUERY)

  const [structure, setStructure] = useState(null)
  const [chapters, setChapters] = useState([])
  const [activeChapterId, setActiveChapterId] = useState(null)
  const [chapterData, setChapterData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [chapterStatus, setChapterStatus] = useState({})

  const [wordNote, setWordNote] = useState(null)
  const [commentParaId, setCommentParaId] = useState(null)
  const [showReview, setShowReview] = useState(false)
  const [tocOpen, setTocOpen] = useState(false)
  const [prefsOpen, setPrefsOpen] = useState(false)
  const [flashParaId, setFlashParaId] = useState(null)
  const [progress, setProgress] = useState(0)

  const progressRef = useRef({})
  const restoreParagraphRef = useRef(null)
  const chapterRequestRef = useRef(0)
  const sheetRef = useRef(null)
  const prefsRef = useRef(null)

  const closeNotes = useCallback(() => {
    setWordNote(null)
    setCommentParaId(null)
  }, [])

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
      if (requestId === chapterRequestRef.current) setError('加载章节失败：' + e.message)
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
    closeNotes()
    setShowReview(false)
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
        const statuses = Object.fromEntries(allChapters.map((ch) => [
          ch.id, ['unread', 'in_progress', 'completed'].includes(prog.chapter_status?.[ch.id])
            ? prog.chapter_status[ch.id] : 'unread',
        ]))
        progressRef.current = statuses
        setChapterStatus(statuses)
        // 生词本“回到原文”通过 ?p= 指定段落，优先于上次阅读位置
        const linkedParagraph = searchParams.get('p')
        const targetParagraph = linkedParagraph || prog.last_paragraph_id || ''
        const targetChapterId = chapterIdFromParagraph(targetParagraph, allChapters) || allChapters[0].id
        restoreParagraphRef.current = targetParagraph
        if (linkedParagraph) setFlashParaId(linkedParagraph)
        setActiveChapterId(targetChapterId)
        await loadChapterContent(targetChapterId)
      } catch (e) {
        if (!cancelled) {
          setError('加载文档失败：' + e.message)
          setLoading(false)
        }
      }
    }
    initialize()
    return () => {
      cancelled = true
      chapterRequestRef.current += 1
    }
  }, [docId]) // searchParams 只在打开文档时读取一次

  useEffect(() => {
    if (!chapterData) return
    const paragraphId = restoreParagraphRef.current
    restoreParagraphRef.current = null
    if (paragraphId) document.getElementById(paragraphId)?.scrollIntoView({ block: 'center' })
  }, [chapterData])

  useEffect(() => {
    if (!flashParaId) return
    const timer = setTimeout(() => setFlashParaId(null), 2400)
    return () => clearTimeout(timer)
  }, [flashParaId])

  // 阅读进度：段落进入视野即记为阅读中，读到最后一段记为读完；2 秒防抖写入。
  useEffect(() => {
    if (!chapterData || chapterData.chapter_id !== activeChapterId) return
    const paragraphs = (chapterData.sections || []).flatMap((sec) => sec.paragraphs || [])
    const lastParaId = paragraphs.at(-1)?.id
    let saveTimer = null
    let pendingProgress = null
    const save = () => {
      if (!pendingProgress) return
      const snapshot = pendingProgress
      pendingProgress = null
      updateProgress(docId, snapshot).catch((e) => console.warn('阅读进度保存失败', e))
    }
    const observer = new IntersectionObserver((entries) => {
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

  // 顶栏进度条：本章滚动位置
  useEffect(() => {
    let frame = 0
    const update = () => {
      frame = 0
      const max = document.documentElement.scrollHeight - window.innerHeight
      setProgress(max > 0 ? Math.min(1, window.scrollY / max) : 0)
    }
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
  }, [chapterData])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Escape') return
      if (prefsOpen) setPrefsOpen(false)
      else if (tocOpen) setTocOpen(false)
      else closeNotes()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [prefsOpen, tocOpen, closeNotes])

  useEffect(() => {
    if (!prefsOpen) return
    const onDown = (e) => { if (!prefsRef.current?.contains(e.target)) setPrefsOpen(false) }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [prefsOpen])

  useEffect(() => { if (railPinned) setTocOpen(false) }, [railPinned])

  // 窄屏：底部面板打开或内容加载变高后，确保被点的词不被面板挡住
  useEffect(() => {
    const sheet = sheetRef.current
    if (wide || !sheet) return
    const ensureVisible = () => {
      const target = wordNote
        ? document.querySelector(`[id="${wordNote.paragraphId}"] .w.is-active`)
        : commentParaId && document.getElementById(commentParaId)
      if (!target) return
      const sheetTop = window.innerHeight - sheet.offsetHeight
      const rect = target.getBoundingClientRect()
      const overlap = (wordNote ? rect.bottom : Math.min(rect.bottom, rect.top + 120)) - (sheetTop - 24)
      if (overlap > 0) window.scrollBy({ top: overlap, behavior: 'smooth' })
    }
    const observer = new ResizeObserver(ensureVisible)
    observer.observe(sheet)
    return () => observer.disconnect()
  }, [wordNote, commentParaId, wide])

  const switchChapter = (chId) => {
    setTocOpen(false)
    if (chId === activeChapterId && chapterData) return
    restoreParagraphRef.current = null
    setActiveChapterId(chId)
    closeNotes()
    setShowReview(false)
    loadChapterContent(chId)
    window.scrollTo(0, 0)
  }

  const jumpToSection = (secId) => {
    setTocOpen(false)
    document.getElementById(secId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const handleParagraphClick = (e, para) => {
    const el = e.target.closest('.w')
    if (!el) return
    const index = Number(el.dataset.i)
    if (wordNote?.paragraphId === para.id && wordNote.index === index) {
      setWordNote(null)
      return
    }
    const row = el.closest('.para-row')
    const offset = row ? el.getBoundingClientRect().top - row.getBoundingClientRect().top : 0
    setWordNote({
      word: el.textContent.replace(/\n/g, ''),
      sentence: para.text,
      paragraphId: para.id,
      index,
      offset,
    })
  }

  const toggleComments = (paraId) => {
    setCommentParaId((current) => (current === paraId ? null : paraId))
  }

  const chapterIndex = chapters.findIndex((ch) => ch.id === activeChapterId)
  const prevChapter = chapterIndex > 0 ? chapters[chapterIndex - 1] : null
  const nextChapter = chapterIndex >= 0 && chapterIndex < chapters.length - 1 ? chapters[chapterIndex + 1] : null
  const sheetOpen = !wide && (wordNote || commentParaId)

  const renderWordGloss = () => wordNote && (
    <WordGloss key={`${wordNote.paragraphId}:${wordNote.index}`}
      word={wordNote.word} sentence={wordNote.sentence}
      docId={docId} paragraphId={wordNote.paragraphId}
      onClose={() => setWordNote(null)} />
  )

  const toc = (
    <Toc title={structure?.title} chapters={chapters} activeChapterId={activeChapterId}
      chapterStatus={chapterStatus} onChapter={switchChapter} onSection={jumpToSection} />
  )

  return (
    <div className={`reader${railPinned ? ' has-rail' : ''}${sheetOpen ? ' has-sheet' : ''}`}>
      <header className="reader-bar">
        <Link to="/" className="icon-btn" aria-label="返回书库"><Icon name="back" /></Link>
        {!railPinned && (
          <button type="button" className="icon-btn" aria-label="目录" aria-expanded={tocOpen}
            onClick={() => setTocOpen((v) => !v)}>
            <Icon name="toc" />
          </button>
        )}
        <div className="reader-title">
          <span className="reader-book">{structure?.title || ''}</span>
          {chapterData?.title && <span className="reader-chapter">{chapterData.title}</span>}
        </div>
        <div className="reader-tools" ref={prefsRef}>
          <button type="button" className="icon-btn" aria-label="阅读设置" aria-expanded={prefsOpen}
            onClick={() => setPrefsOpen((v) => !v)}>
            <Icon name="type" />
          </button>
          {prefsOpen && (
            <div className="popover" role="dialog" aria-label="阅读设置">
              <ReadingPrefsPanel />
            </div>
          )}
        </div>
        <div className="reader-progress" aria-hidden="true">
          <span style={{ transform: `scaleX(${progress})` }} />
        </div>
      </header>

      {railPinned && <aside className="reader-rail">{toc}</aside>}
      {!railPinned && tocOpen && (
        <>
          <div className="scrim" onClick={() => setTocOpen(false)} />
          <aside className="reader-drawer">{toc}</aside>
        </>
      )}

      <main className="reader-main">
        {error && <div className="notice reader-error"><Icon name="info" />{error}</div>}
        {loading && (
          <div className="chapter">
            <div className="skeleton chapter-skeleton"><span /><span /><span /><span /><span /></div>
          </div>
        )}

        {chapterData && !loading && (
          <article className={`chapter${wide ? ' is-wide' : ''}`}>
            <header className="chapter-head">
              {chapterIndex >= 0 && <div className="chapter-kicker">第 {chapterIndex + 1} 章 · 共 {chapters.length} 章</div>}
              <h1 className="chapter-title" lang="en">{chapterData.title}</h1>
            </header>

            {chapterData.sections?.map((sec) => (
              <section key={sec.id} id={sec.id} className="section">
                {sec.title && <h2 className="section-title" lang="en">{sec.title}</h2>}
                {sec.paragraphs?.map((para) => {
                  const commentsOpen = commentParaId === para.id
                  const glossHere = wordNote?.paragraphId === para.id
                  return (
                    <div key={para.id} id={para.id}
                      className={`para-row${flashParaId === para.id ? ' is-flash' : ''}${commentsOpen ? ' is-annotated' : ''}`}>
                      <p className="para" lang="en" onClick={(e) => handleParagraphClick(e, para)}>
                        <ParagraphText text={para.text} activeIndex={glossHere ? wordNote.index : null} />
                      </p>
                      <div className="para-margin">
                        <button type="button" className={`margin-btn${commentsOpen ? ' on' : ''}`}
                          aria-expanded={commentsOpen} aria-label="本段评论"
                          onClick={() => toggleComments(para.id)}>
                          <Icon name="comment" size={16} />
                          {wide && <span>评论</span>}
                        </button>
                        {wide && (glossHere || commentsOpen) && (
                          // 批注浮在页边，不撑高段落，正文排版不被打断
                          <div className="margin-notes">
                            {glossHere && (
                              <div className="margin-slot" style={{ marginTop: Math.max(0, wordNote.offset - 36) }}>
                                {renderWordGloss()}
                              </div>
                            )}
                            {commentsOpen && (
                              <div className="margin-slot">
                                <ParagraphComments docId={docId} paragraphId={para.id} onClose={() => setCommentParaId(null)} />
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                      {chapterData.images?.filter((img) => img.after_paragraph === para.id).map((img) => (
                        <figure key={img.id} className="figure">
                          <img src={img.url} alt={img.caption || '插图'} loading="lazy" />
                          {img.caption && <figcaption>{img.caption}</figcaption>}
                        </figure>
                      ))}
                    </div>
                  )
                })}
              </section>
            ))}

            <footer className="chapter-end">
              <div className="chapter-end-rule"><span>本章完</span></div>
              {showReview
                ? <ChapterReview docId={docId} chapterId={activeChapterId} />
                : (
                  <button type="button" className="btn review-cta" onClick={() => setShowReview(true)}>
                    <Icon name="sparkle" size={16} />生成章节回顾
                  </button>
                )}
              <nav className="chapter-nav" aria-label="章节切换">
                {prevChapter ? (
                  <button type="button" onClick={() => switchChapter(prevChapter.id)}>
                    <span className="cn-dir"><Icon name="prev" size={15} />上一章</span>
                    <span className="cn-title">{prevChapter.title}</span>
                  </button>
                ) : <span />}
                {nextChapter && (
                  <button type="button" className="is-next" onClick={() => switchChapter(nextChapter.id)}>
                    <span className="cn-dir">下一章<Icon name="next" size={15} /></span>
                    <span className="cn-title">{nextChapter.title}</span>
                  </button>
                )}
              </nav>
            </footer>
          </article>
        )}

        {!loading && !chapterData && !error && (
          <div className="chapter"><p className="reader-empty">这份文档没有可显示的内容。</p></div>
        )}
      </main>

      {sheetOpen && (
        <BottomSheet ref={sheetRef} label="批注">
          {renderWordGloss()}
          {commentParaId && (
            <ParagraphComments docId={docId} paragraphId={commentParaId} onClose={() => setCommentParaId(null)} />
          )}
        </BottomSheet>
      )}
    </div>
  )
}
