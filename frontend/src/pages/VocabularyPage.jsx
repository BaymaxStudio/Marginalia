import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listVocabulary, listDocuments } from '../services/api'
import './VocabularyPage.css'

export default function VocabularyPage() {
  const navigate = useNavigate()
  const [words, setWords] = useState([])
  const [sort, setSort] = useState('time_desc')
  const [docFilter, setDocFilter] = useState('')
  const [docs, setDocs] = useState([])

  useEffect(() => {
    listDocuments().then((d) => setDocs(d.documents || [])).catch(() => {})
  }, [])

  useEffect(() => {
    const params = { sort }
    if (docFilter) params.document_id = docFilter
    listVocabulary(params).then((d) => setWords(d.words || [])).catch(() => {})
  }, [sort, docFilter])

  return (
    <div className="vocab-page">
      <header className="vocab-header">
        <button className="btn-back" onClick={() => navigate('/')}>← 返回</button>
        <h1>生词本</h1>
      </header>

      <div className="vocab-controls">
        <select value={docFilter} onChange={(e) => setDocFilter(e.target.value)}>
          <option value="">全部文档</option>
          {docs.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="time_desc">最近查询</option>
          <option value="time_asc">最早查询</option>
          <option value="alpha_asc">A → Z</option>
          <option value="alpha_desc">Z → A</option>
        </select>
      </div>

      {words.length === 0 && (
        <p className="empty">生词本为空。开始阅读并点击单词，查过的词会自动收入这里。</p>
      )}

      <div className="vocab-list">
        {words.map((w) => (
          <div key={w.id} className="vocab-card">
            <div className="vocab-head">
              <h3>{w.word_lemma}</h3>
              {w.phonetic && <span className="phonetic">{w.phonetic}</span>}
              <span className="count">查 {w.lookup_count} 次</span>
            </div>
            <p className="vocab-sentence">"{w.sentence}"</p>
            {w.ai_explanation && <p className="vocab-explain">{w.ai_explanation}</p>}
            {w.domain && <span className="vocab-domain">{w.domain}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
