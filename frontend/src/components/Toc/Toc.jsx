import Icon from '../Icon/Icon'
import './Toc.css'

const STATUS_LABEL = { completed: '已读完', in_progress: '阅读中', unread: '未读' }

export default function Toc({ title, chapters, activeChapterId, chapterStatus, onChapter, onSection }) {
  const done = chapters.filter((ch) => chapterStatus[ch.id] === 'completed').length
  return (
    <nav className="toc" aria-label="目录">
      <div className="toc-book">
        <Icon name="book" size={16} />
        <span>{title || '加载中…'}</span>
      </div>
      {chapters.length > 0 && (
        <div className="toc-progress">
          <div className="toc-bar"><span style={{ width: `${(done / chapters.length) * 100}%` }} /></div>
          <span>{done} / {chapters.length} 章</span>
        </div>
      )}
      <ol className="toc-list">
        {chapters.map((ch, index) => {
          const status = chapterStatus[ch.id] || 'unread'
          const active = ch.id === activeChapterId
          return (
            <li key={ch.id}>
              <button type="button" className={`toc-chapter ${active ? 'active' : ''}`}
                aria-current={active ? 'true' : undefined} onClick={() => onChapter(ch.id)}>
                <span className={`toc-dot ${status}`} title={STATUS_LABEL[status]}>
                  <span className="sr-only">{STATUS_LABEL[status]}</span>
                </span>
                <span className="toc-no">{index + 1}</span>
                <span className="toc-name">{ch.title}</span>
              </button>
              {active && ch.sections?.some((s) => s.title) && (
                <ol className="toc-sections">
                  {ch.sections.filter((s) => s.title).map((sec) => (
                    <li key={sec.id}>
                      <button type="button" onClick={() => onSection(sec.id)}>{sec.title}</button>
                    </li>
                  ))}
                </ol>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
