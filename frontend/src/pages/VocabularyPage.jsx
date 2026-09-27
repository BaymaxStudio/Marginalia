import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listVocabulary, listDocuments } from '../services/api'
import AppHeader from '../components/AppHeader/AppHeader'
import Icon from '../components/Icon/Icon'
import './VocabularyPage.css'

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// 后端存的是整段原文，这里只取包含该词的那一句，并把词标出来
function excerpt(paragraph, lemma) {
  const text = (paragraph || '').replace(/\s+/g, ' ').trim()
  const stem = lemma.length > 4 ? lemma.slice(0, -1) : lemma
  const wordRe = new RegExp(`\\b${escapeRe(stem)}[\\w'’-]*`, 'i')
  const sentences = text.split(/(?<=[.!?])\s+/)
  let sentence = sentences.find((s) => wordRe.test(s)) || text
  if (sentence.length > 260) {
    const at = Math.max(0, sentence.search(wordRe) - 100)
    sentence = (at > 0 ? '…' : '') + sentence.slice(at, at + 240) + '…'
  }
  const match = sentence.match(wordRe)
  if (!match) return [sentence]
  const i = match.index
  return [sentence.slice(0, i), <mark key="m">{match[0]}</mark>, sentence.slice(i + match[0].length)]
}

export default function VocabularyPage() {
  const [words, setWords] = useState(null)
  const [docs, setDocs] = useState([])
  const [sort, setSort] = useState('time_desc')
  const [docFilter, setDocFilter] = useState('')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    listDocuments().then((d) => setDocs(d.documents || []))
      .catch((e) => console.warn('读取书目失败', e))
  }, [])

  useEffect(() => {
    const params = { sort }
    if (docFilter) params.document_id = docFilter
    listVocabulary(params)
      .then((d) => { setWords(d.words || []); setError('') })
      .catch((e) => { setWords([]); setError('生词本加载失败：' + e.message) })
  }, [sort, docFilter])

  const titleById = useMemo(() => Object.fromEntries(docs.map((d) => [d.id, d.title])), [docs])
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!words || !q) return words || []
    return words.filter((w) => w.word_lemma.toLowerCase().includes(q)
      || (w.selected_meaning || '').includes(q) || (w.ai_explanation || '').includes(q))
  }, [words, query])

  return (
    <div className="vocab">
      <AppHeader />
      <main className="page">
        <div className="page-head">
          <div>
            <h1 className="page-title">生词本</h1>
            <p className="page-sub">{words ? `${words.length} 个词 · 查过的词会自动收进来` : '加载中…'}</p>
          </div>
        </div>

        <div className="vocab-controls">
          <label className="vocab-search">
            <Icon name="search" size={16} />
            <input className="input" type="search" placeholder="搜索单词或释义" aria-label="搜索生词"
              value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          <select className="select" value={docFilter} onChange={(e) => setDocFilter(e.target.value)} aria-label="按书筛选">
            <option value="">全部书目</option>
            {docs.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
          </select>
          <select className="select" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="排序">
            <option value="time_desc">最近查询</option>
            <option value="time_asc">最早查询</option>
            <option value="alpha_asc">A → Z</option>
            <option value="alpha_desc">Z → A</option>
          </select>
        </div>

        {error && <div className="notice" role="alert"><Icon name="info" />{error}</div>}

        {words && words.length === 0 && !error && (
          <div className="vocab-empty">
            <strong>生词本还是空的</strong>
            <p>在阅读时点击任何一个英文单词，查过的词和它所在的句子会自动收到这里。</p>
            <Link to="/" className="btn">去书库</Link>
          </div>
        )}
        {words && words.length > 0 && visible.length === 0 && (
          <p className="vocab-none">没有匹配 “{query}” 的词。</p>
        )}

        <ul className="entries">
          {visible.map((w) => (
            <li key={w.id} className="entry">
              <div className="entry-word">
                <span className="entry-lemma" lang="en">{w.word_lemma}</span>
                {w.phonetic && <span className="entry-phonetic">/{w.phonetic}/</span>}
              </div>
              <div className="entry-body">
                {w.selected_meaning && <div className="entry-meaning">{w.selected_meaning.replace(/^[a-z]+\.\s*/i, '')}</div>}
                {w.sentence && <blockquote className="entry-quote" lang="en">{excerpt(w.sentence, w.word_lemma)}</blockquote>}
                {w.ai_explanation && <p className="entry-explain">{w.ai_explanation}</p>}
                <div className="entry-meta">
                  {w.domain && <span className="tag">{w.domain}</span>}
                  <span>查过 {w.lookup_count} 次</span>
                  {titleById[w.document_id] && <span>《{titleById[w.document_id]}》</span>}
                  {w.document_id && w.paragraph_id && titleById[w.document_id] && (
                    <Link className="entry-jump" to={`/reader/${w.document_id}?p=${encodeURIComponent(w.paragraph_id)}`}>
                      回到原文<Icon name="arrowOut" size={14} />
                    </Link>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </main>
    </div>
  )
}
