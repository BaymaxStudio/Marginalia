import { useState, useEffect } from 'react'
import { chapterReview } from '../../services/api'
import './ChapterReview.css'

export default function ChapterReview({ docId, chapterId }) {
  const [review, setReview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    setError('')
    chapterReview({ document_id: docId, chapter_id: chapterId })
      .then((d) => setReview(d))
      .catch((e) => setError('章节回顾生成失败：' + e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [docId, chapterId])

  if (loading) return <div className="review-card"><p className="rev-loading">领读学长正在回顾章节...</p></div>
  if (error) return (
    <div className="review-card">
      <p className="rev-error">{error}</p>
      <button className="btn-swap" onClick={load}>重试</button>
    </div>
  )
  if (!review) return null

  return (
    <div className="review-card">
      <div className="rev-avatar">📚</div>
      <h3 className="rev-title">章节回顾 · 领读学长</h3>

      <section className="rev-section">
        <h4>论证主线</h4>
        <p>{review.main_argument}</p>
      </section>

      <section className="rev-section">
        <h4>关键收获</h4>
        <ul>
          {review.key_takeaways?.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
      </section>

      <section className="rev-section">
        <h4>章节衔接</h4>
        <p>{review.connection_to_previous}</p>
      </section>

      <section className="rev-section">
        <h4>前瞻提示</h4>
        <p>{review.preview_next}</p>
      </section>

      {review.summarized && (
        <p className="rev-summary-note">本章较长，回顾基于章节摘要生成</p>
      )}
    </div>
  )
}
