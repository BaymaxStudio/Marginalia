import { useState, useEffect, useRef } from 'react'
import { dictionaryLookup, aiLookup } from '../../services/api'
import './WordCard.css'

export default function WordCard({ word, sentence, docId, paragraphId, x, y, onClose }) {
  const [dictData, setDictData] = useState(null)
  const [aiData, setAiData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const cardRef = useRef(null)

  useEffect(() => {
    const clean = word.replace(/[^a-zA-Z'’-]/g, '')
    if (!clean) { onClose(); return }
    dictionaryLookup(clean)
      .then((d) => { if (d.found) setDictData(d); else setError('词典未收录该词') })
      .catch(() => setError('词典查询失败'))
  }, [word])

  useEffect(() => {
    const clean = word.replace(/[^a-zA-Z'’-]/g, '')
    if (!clean || !dictData) return
    setLoading(true)
    setError('')
    aiLookup({ document_id: docId, paragraph_id: paragraphId, word: clean, sentence, mode: 'context' })
      .then((d) => {
        if (d.ai_context) setAiData(d.ai_context)
        else setError('AI 解释暂时不可用')
      })
      .catch(() => setError('AI 请求失败'))
      .finally(() => setLoading(false))
  }, [dictData])

  useEffect(() => {
    if (!cardRef.current) return
    const rect = cardRef.current.getBoundingClientRect()
    let top = y, left = x - 180
    if (rect.right > window.innerWidth - 20) left = window.innerWidth - rect.width - 20
    if (left < 20) left = 20
    if (rect.bottom > window.innerHeight - 20) top = y - rect.height - 20
    cardRef.current.style.top = top + 'px'
    cardRef.current.style.left = left + 'px'
  }, [dictData, aiData])

  useEffect(() => {
    const handler = (e) => {
      if (cardRef.current && !cardRef.current.contains(e.target)) onClose()
    }
    setTimeout(() => document.addEventListener('click', handler), 100)
    return () => document.removeEventListener('click', handler)
  }, [])

  if (!dictData && !error) return null

  return (
    <div ref={cardRef} className="word-card" style={{ top: y, left: x - 180 }}>
      <button className="wc-close" onClick={onClose}>×</button>

      {error && !dictData && <div className="wc-error">{error}</div>}

      {dictData && (
        <div className="wc-dict">
          <div className="wc-head">
            <h3>{dictData.word_lemma}</h3>
            {dictData.phonetic && <span className="wc-phonetic">{dictData.phonetic}</span>}
          </div>
          <ul className="wc-entries">
            {dictData.dictionary_entries?.map((e) => (
              <li key={e.index} className={aiData?.selected_index === e.index ? 'active' : ''}>
                <span className="wc-pos">{e.pos}</span>
                <span className="wc-zh">{e.zh}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="wc-ai">
        {loading && <p className="wc-loading">AI 分析中...</p>}
        {error && dictData && <p className="wc-error-inline">{error}</p>}
        {aiData && (
          <>
            <p className="wc-explain">
              {aiData.is_technical_term && <span className="wc-tag-term">学科术语</span>}
              {aiData.explanation}
            </p>
            {aiData.domain && <span className="wc-domain">{aiData.domain}</span>}
          </>
        )}
      </div>
    </div>
  )
}
