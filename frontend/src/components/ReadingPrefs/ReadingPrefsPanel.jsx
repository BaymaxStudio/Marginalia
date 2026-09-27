import { usePrefs } from '../../prefs/PrefsContext'
import Icon from '../Icon/Icon'
import './ReadingPrefsPanel.css'

const THEMES = [
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
  { value: 'system', label: '跟随系统' },
]

function Stepper({ label, value, display, min, max, step, onChange }) {
  const round = (v) => Math.round(v * 10) / 10
  return (
    <div className="rp-row">
      <span className="rp-label">{label}</span>
      <div className="rp-stepper">
        <button type="button" className="icon-btn" aria-label={`减小${label}`}
          disabled={value <= min} onClick={() => onChange(round(Math.max(min, value - step)))}>
          <Icon name="minus" />
        </button>
        <output className="rp-value">{display}</output>
        <button type="button" className="icon-btn" aria-label={`增大${label}`}
          disabled={value >= max} onClick={() => onChange(round(Math.min(max, value + step)))}>
          <Icon name="plus" />
        </button>
      </div>
    </div>
  )
}

export default function ReadingPrefsPanel({ preview = false }) {
  const { prefs, updatePrefs, saveError } = usePrefs()
  return (
    <div className="rp">
      <Stepper label="字号" value={prefs.font_size} display={`${prefs.font_size}px`}
        min={14} max={28} step={1} onChange={(v) => updatePrefs({ font_size: v })} />
      <Stepper label="行高" value={prefs.line_height} display={prefs.line_height.toFixed(1)}
        min={1.4} max={2.4} step={0.1} onChange={(v) => updatePrefs({ line_height: v })} />
      <div className="rp-row">
        <span className="rp-label">主题</span>
        <div className="seg" role="radiogroup" aria-label="主题">
          {THEMES.map((t) => (
            <button key={t.value} type="button" role="radio" aria-checked={prefs.theme === t.value}
              onClick={() => updatePrefs({ theme: t.value })}>{t.label}</button>
          ))}
        </div>
      </div>
      {preview && (
        <p className="rp-preview" lang="en">
          Marginal notes, far from being idle scribbles, record a dialogue between reader and author.
        </p>
      )}
      {saveError ? <p className="error-text">{saveError}</p> : <p className="rp-hint">改动立即生效并自动保存</p>}
    </div>
  )
}
