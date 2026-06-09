import { useState, useEffect } from 'react'
import { paragraphCommentary } from '../../services/api'
import './CommentPanel.css'

const AVATARS = {
  '领读学长': '📚',
  '术语侦探': '🔍',
  '批判者': '⚡',
  '联想家': '💡',
  '文化翻译官': '🌍',
  '历史档案员': '📜',
}

export default function CommentPanel({ docId, paragraphId, onClose }) {
  const [comments, setComments] = useState([])
  const [personas, setPersonas] = useState([])
  const [loading, setLoading] = useState(true)
  const [excluded, setExcluded] = useState([])

  const fetchComments = async (excludeList = []) => {
    setLoading(true)
    try {
      const data = await paragraphCommentary({
        document_id: docId,
        paragraph_id: paragraphId,
        excluded_personas: excludeList,
      })
      setPersonas(data.selected_personas || [])
      setComments(data.comments || [])
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { fetchComments([]) }, [docId, paragraphId])

  const handleSwap = () => {
    const newExcluded = [...excluded, ...personas]
    setExcluded(newExcluded)
    fetchComments(newExcluded)
  }

  return (
    <div className="comment-panel">
      <div className="cp-header">
        <span className="cp-title">阅读评论</span>
        <button className="cp-close" onClick={onClose}>×</button>
      </div>

      {loading && <p className="cp-loading">正在生成评论...</p>}

      {!loading && comments.map((c, i) => (
        <div key={i} className="comment-item">
          <div className="comment-avatar">{AVATARS[c.persona] || '💬'}</div>
          <div className="comment-body">
            <span className="comment-persona">{c.persona}</span>
            <p className="comment-text">{c.comment}</p>
          </div>
        </div>
      ))}

      {!loading && comments.length > 0 && (
        <button className="btn-swap" onClick={handleSwap}>
          🔄 换一批视角
        </button>
      )}
    </div>
  )
}
