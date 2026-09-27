import { useEffect, useState } from 'react'
import { chapterReview } from '../../services/api'
import Icon from '../Icon/Icon'
import ErrorMessage from '../Notes/ErrorMessage'
import './ChapterReview.css'

// 章末回顾：领读学长梳理本章论证主线、收获和前后衔接。
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

  return (
    <section className="review" aria-label="章节回顾">
      <div className="review-kicker"><Icon name="sparkle" size={15} />章节回顾 · 领读学长</div>

      {loading && <div className="skeleton review-skeleton"><span /><span /><span /></div>}

      {!loading && error && (
        <div className="review-error">
          <ErrorMessage message={error} />
          <button type="button" className="btn btn-sm" onClick={load}>
            <Icon name="refresh" size={15} />重试
          </button>
        </div>
      )}

      {!loading && !error && review && (
        <div className="review-body">
          <div className="review-block review-lead">
            <h4>论证主线</h4>
            <p>{review.main_argument}</p>
          </div>
          {review.key_takeaways?.length > 0 && (
            <div className="review-block">
              <h4>关键收获</h4>
              <ol>{review.key_takeaways.map((t, i) => <li key={i}>{t}</li>)}</ol>
            </div>
          )}
          {review.connection_to_previous && (
            <div className="review-block">
              <h4>与前文的衔接</h4>
              <p>{review.connection_to_previous}</p>
            </div>
          )}
          {review.preview_next && (
            <div className="review-block">
              <h4>下一章预告</h4>
              <p>{review.preview_next}</p>
            </div>
          )}
          {review.summarized && <p className="review-note">本章较长，回顾基于章节摘要生成。</p>}
        </div>
      )}
    </section>
  )
}
