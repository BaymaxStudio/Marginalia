import { useState, useEffect, useRef } from 'react'
import { dictionaryLookup, aiLookup } from '../../services/api'
import './WordCard.css'

export default function WordCard({ word, sentence, docId, paragraphId, x, y, onClose }) {
  const [dictData, setDictData] = useState(null)
  const [aiData, setAiData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const cardRef = useRef(null)

  const onCloseRef = useRef(onClose)
  useEffect(() => { onCloseRef.current = onClose }, [onClose])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const clean = word.replace(/[^a-zA-Z'’-]/g, '')
    setDictData(null)
    setAiData(null)
    setError('')
    setLoading(false)
    if (!clean) { onCloseRef.current(); return }

    async function lookup() {
      let dictionary
      try {
        dictionary = await dictionaryLookup(clean, { signal: controller.signal })
      } catch (err) {
        if (active && err.name !== 'AbortError') setError('词典查询失败')
        return
      }
      if (!active) return
      if (!dictionary.found) {
        setError('词典未收录该词')
        return
      }
      setDictData(dictionary)
      setLoading(true)
      try {
        const result = await aiLookup({ document_id: docId, paragraph_id: paragraphId, word: clean, sentence, mode: 'context' }, { signal: controller.signal })
        if (!active) return
        if (result.ai_context) setAiData(result.ai_context)
        else setError('AI 解释暂时不可用')
      } catch (err) {
        if (active && err.name !== 'AbortError') setError('AI 请求失败')
      } finally {
        if (active) setLoading(false)
      }
    }
    lookup()
    return () => {
      active = false
      controller.abort()
    }
  }, [word, sentence, docId, paragraphId])

  useEffect(() => {
    if (!cardRef.current) return
    const rect = cardRef.current.getBoundingClientRect()
    const left = Math.max(20, Math.min(x - 180, window.innerWidth - rect.width - 20))
    const top = Math.max(20, y + rect.height > window.innerHeight - 20 ? y - rect.height - 20 : y)
    cardRef.current.style.top = top + 'px'
    cardRef.current.style.left = left + 'px'
  }, [dictData, aiData, error, loading, x, y])

  useEffect(() => {
    const handler = (e) => {
      if (cardRef.current && !cardRef.current.contains(e.target)) onCloseRef.current()
    }
    const timer = setTimeout(() => document.addEventListener('click', handler), 100)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('click', handler)
    }
  }, [])

  return (
    <div ref={cardRef} className="word-card" style={{ top: y, left: x - 180 }}>
      <button className="wc-close" onClick={onClose}>×</button>

      {!dictData && !error && <div className="wc-dict wc-loading">词典查询中...</div>}
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
