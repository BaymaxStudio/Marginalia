import { useEffect, useState } from 'react'
import { dictionaryLookup, aiLookup } from '../../services/api'
import Icon from '../Icon/Icon'
import ErrorMessage from './ErrorMessage'
import './Notes.css'

// 查词批注：先给词典释义，再由 AI 结合所在句子挑出语境义。
export default function WordGloss({ word, sentence, docId, paragraphId, onClose }) {
  const [dict, setDict] = useState(null)
  const [ai, setAi] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [error, setError] = useState('')
  const clean = word.replace(/[^a-zA-Z'’-]/g, '')

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setDict(null)
    setAi(null)
    setError('')
    setAiLoading(false)

    async function lookup() {
      let dictionary
      try {
        dictionary = await dictionaryLookup(clean, { signal: controller.signal })
      } catch (e) {
        if (active && e.name !== 'AbortError') setError('词典查询失败：' + e.message)
        return
      }
      if (!active) return
      if (!dictionary.found) {
        setError(`词典未收录 “${clean}”`)
        return
      }
      setDict(dictionary)
      setAiLoading(true)
      try {
        const result = await aiLookup({
          document_id: docId, paragraph_id: paragraphId, word: clean, sentence, mode: 'context',
        }, { signal: controller.signal })
        if (!active) return
        if (result.ai_context) setAi(result.ai_context)
        else setError(result.ai_error || 'AI 解释暂时不可用，请稍后重试。')
      } catch (e) {
        if (active && e.name !== 'AbortError') setError('AI 解释失败：' + e.message)
      } finally {
        if (active) setAiLoading(false)
      }
    }
    if (clean) lookup()
    return () => {
      active = false
      controller.abort()
    }
  }, [clean, sentence, docId, paragraphId])

  return (
    <aside className="note is-accent" aria-label={`${clean} 的释义`}>
      <button type="button" className="icon-btn note-close" onClick={onClose} aria-label="关闭释义">
        <Icon name="close" />
      </button>
      <div className="note-head">
        <span className="note-title" lang="en">{dict?.word_lemma || clean}</span>
        {dict?.phonetic && <span className="note-sub">/{dict.phonetic}/</span>}
      </div>

      {!dict && !error && <div className="skeleton"><span /><span /></div>}

      {dict && (
        <ul className="senses">
          {dict.dictionary_entries?.filter((e) => e.zh?.trim()).map((e) => (
            <li key={e.index} className={ai?.selected_index === e.index ? 'picked' : ''}>
              {e.pos && <span className="sense-pos">{e.pos}</span>}
              <span>{e.zh.replace(/^[a-z]+\.\s*/i, '')}</span>
            </li>
          ))}
        </ul>
      )}

      {dict && (aiLoading || ai) && (
        <div className="gloss-ai">
          {aiLoading && <div className="skeleton"><span /><span /><span /></div>}
          {ai && (
            <>
              <p>{ai.explanation}</p>
              {(ai.is_technical_term || ai.domain) && (
                <div className="note-foot">
                  {ai.is_technical_term && <span className="tag is-accent">学科术语</span>}
                  {ai.domain && <span className="tag">{ai.domain}</span>}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {error && <ErrorMessage message={error} />}
    </aside>
  )
}
