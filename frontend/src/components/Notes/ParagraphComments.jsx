import { useEffect, useState } from 'react'
import { paragraphCommentary } from '../../services/api'
import Icon from '../Icon/Icon'
import ErrorMessage from './ErrorMessage'
import './Notes.css'

// 段落评论：2-3 位 AI 读者从不同角度批注这一段，可以换一批视角。
export default function ParagraphComments({ docId, paragraphId, onClose }) {
  const [comments, setComments] = useState([])
  const [personas, setPersonas] = useState([])
  const [excluded, setExcluded] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchComments = async (excludeList) => {
    setLoading(true)
    setError('')
    try {
      const data = await paragraphCommentary({
        document_id: docId,
        paragraph_id: paragraphId,
        excluded_personas: excludeList,
      })
      setPersonas(data.selected_personas || [])
      setComments(data.comments || [])
    } catch (e) {
      setError('评论生成失败：' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setExcluded([])
    fetchComments([])
  }, [docId, paragraphId])

  const swap = () => {
    const next = [...excluded, ...personas]
    setExcluded(next)
    fetchComments(next)
  }

  return (
    <aside className="note" aria-label="本段评论">
      <button type="button" className="icon-btn note-close" onClick={onClose} aria-label="关闭评论">
        <Icon name="close" />
      </button>
      <div className="note-head"><span className="note-kicker">本段评论</span></div>

      {loading && <div className="skeleton"><span /><span /><span /></div>}

      {!loading && error && (
        <>
          <ErrorMessage message={error} />
          {/* 换一批失败时 excluded 已更新，重试的仍是换批请求 */}
          <div className="note-foot">
            <button type="button" className="btn btn-sm" onClick={() => fetchComments(excluded)}>
              <Icon name="refresh" size={15} />重试
            </button>
          </div>
        </>
      )}

      {!loading && !error && (
        <>
          <div className="comments">
            {comments.map((c, i) => (
              <div key={i} className="comment">
                <span className="persona-mark" aria-hidden="true">{c.persona.slice(0, 1)}</span>
                <div>
                  <div className="comment-who">{c.persona}</div>
                  <p className="comment-text">{c.comment}</p>
                </div>
              </div>
            ))}
          </div>
          {comments.length > 0 && excluded.length + personas.length < 6 && (
            <div className="note-foot">
              <button type="button" className="btn btn-sm btn-quiet" onClick={swap}>
                <Icon name="refresh" size={15} />换一批视角
              </button>
            </div>
          )}
        </>
      )}
    </aside>
  )
}
