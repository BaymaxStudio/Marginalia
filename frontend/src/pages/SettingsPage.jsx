import { useEffect, useState } from 'react'
import { getSettings, updateSettings } from '../services/api'
import { usePrefs } from '../prefs/PrefsContext'
import AppHeader from '../components/AppHeader/AppHeader'
import Icon from '../components/Icon/Icon'
import ReadingPrefsPanel from '../components/ReadingPrefs/ReadingPrefsPanel'
import './SettingsPage.css'

const PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek', desc: '国内直连，使用 deepseek-chat', keyUrl: 'https://platform.deepseek.com' },
  { value: 'claude', label: 'Claude', desc: 'Anthropic，查词用 Haiku、评论用 Sonnet', keyUrl: 'https://console.anthropic.com' },
  { value: 'openai_compat', label: 'OpenAI 兼容', desc: '自定义服务地址和模型名' },
]

// 服务端不回传 Key 原文；空值提交时后端保持原值不变
const EMPTY_KEYS = { api_key_claude: '', api_key_deepseek: '', api_key_openai_compat: '' }

export default function SettingsPage() {
  const { refresh } = usePrefs()
  const [form, setForm] = useState({
    ai_provider: 'claude',
    ...EMPTY_KEYS,
    openai_compat_base_url: '',
    openai_compat_model_name: '',
  })
  const [configuredKeys, setConfiguredKeys] = useState({})
  const [logLevel, setLogLevel] = useState('INFO')
  const [status, setStatus] = useState({ state: 'idle', message: '' })
  const [logStatus, setLogStatus] = useState('')

  useEffect(() => {
    getSettings().then((s) => {
      setConfiguredKeys(s.api_keys_configured || {})
      setLogLevel(s.log_level || 'INFO')
      setForm((f) => ({
        ...f,
        ai_provider: s.ai_provider || f.ai_provider,
        openai_compat_base_url: s.openai_compat_base_url || '',
        openai_compat_model_name: s.openai_compat_model_name || '',
      }))
    }).catch((e) => setStatus({ state: 'error', message: '读取设置失败：' + e.message }))
  }, [])

  const set = (k, v) => {
    setForm((f) => ({ ...f, [k]: v }))
    if (status.state !== 'saving') setStatus({ state: 'idle', message: '' })
  }

  const saveAi = async (e) => {
    e.preventDefault()
    setStatus({ state: 'saving', message: '' })
    try {
      await updateSettings(form)
    } catch (err) {
      setStatus({ state: 'error', message: '保存失败：' + err.message })
      return
    }
    setForm((f) => ({ ...f, ...EMPTY_KEYS }))
    setStatus({ state: 'saved', message: '已保存' })
    refresh()
    getSettings()
      .then((s) => setConfiguredKeys(s.api_keys_configured || {}))
      .catch((err) => console.warn('刷新 API Key 状态失败', err))
  }

  const saveLogLevel = (value) => {
    setLogLevel(value)
    setLogStatus('')
    updateSettings({ log_level: value })
      .then(() => setLogStatus('已保存'))
      .catch((err) => setLogStatus('保存失败：' + err.message))
  }

  const provider = PROVIDERS.find((p) => p.value === form.ai_provider) || PROVIDERS[0]
  const keyField = `api_key_${form.ai_provider}`
  const keySaved = configuredKeys[form.ai_provider]

  return (
    <div className="settings">
      <AppHeader />
      <main className="page settings-page">
        <div className="page-head">
          <div>
            <h1 className="page-title">设置</h1>
            <p className="page-sub">所有内容只保存在这台电脑上</p>
          </div>
        </div>

        <form className="panel" onSubmit={saveAi}>
          <div className="panel-head">
            <h2>AI 服务</h2>
            <p>语境释义、段落评论和章节回顾会调用这里配置的服务。词典查词不需要联网。</p>
          </div>

          <div className="providers" role="radiogroup" aria-label="AI 服务商">
            {PROVIDERS.map((p) => (
              <label key={p.value} className={`provider${form.ai_provider === p.value ? ' selected' : ''}`}>
                <input type="radio" name="provider" value={p.value} className="sr-only"
                  checked={form.ai_provider === p.value} onChange={(e) => set('ai_provider', e.target.value)} />
                <span className="provider-name">
                  {p.label}
                  {configuredKeys[p.value] && <span className="provider-ok"><Icon name="check" size={13} />已配置</span>}
                </span>
                <span className="provider-desc">{p.desc}</span>
              </label>
            ))}
          </div>

          <div className="panel-fields">
            <label className="field">
              <span className="field-label">{provider.label} API Key</span>
              <input className="input" type="password" autoComplete="off" spellCheck="false"
                placeholder={keySaved ? '已保存，留空则保持不变' : '粘贴你的 API Key'}
                value={form[keyField] || ''} onChange={(e) => set(keyField, e.target.value)} />
              {provider.keyUrl && (
                <span className="field-hint">
                  还没有 Key？到 <a href={provider.keyUrl} target="_blank" rel="noopener noreferrer">{provider.keyUrl.replace('https://', '')}</a> 申请。
                </span>
              )}
            </label>
            {form.ai_provider === 'openai_compat' && (
              <div className="field-pair">
                <label className="field">
                  <span className="field-label">服务地址</span>
                  <input className="input" type="url" placeholder="https://api.openai.com/v1"
                    value={form.openai_compat_base_url} onChange={(e) => set('openai_compat_base_url', e.target.value)} />
                </label>
                <label className="field">
                  <span className="field-label">模型名</span>
                  <input className="input" placeholder="gpt-4o"
                    value={form.openai_compat_model_name} onChange={(e) => set('openai_compat_model_name', e.target.value)} />
                </label>
              </div>
            )}
          </div>

          <div className="panel-foot">
            {status.message && (
              <span className={status.state === 'error' ? 'error-text' : 'save-ok'} role="status">
                {status.state === 'saved' && <Icon name="check" size={15} />}{status.message}
              </span>
            )}
            <button type="submit" className="btn btn-primary" disabled={status.state === 'saving'}>
              {status.state === 'saving' ? '保存中…' : '保存'}
            </button>
          </div>
        </form>

        <section className="panel">
          <div className="panel-head">
            <h2>阅读</h2>
            <p>在阅读页顶栏的 <span className="kbd">Aa</span> 按钮里也能随时调整。</p>
          </div>
          <ReadingPrefsPanel preview />
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>开发日志</h2>
            <p>排查问题时可以临时调到“详细”，日志会记录发给 AI 的完整内容。</p>
          </div>
          <div className="log-row">
            <select className="select" value={logLevel} onChange={(e) => saveLogLevel(e.target.value)} aria-label="日志级别">
              <option value="INFO">标准：操作流水和异常</option>
              <option value="DEBUG">详细：包含 AI 提示词和内部决策</option>
            </select>
            {logStatus && <span className={logStatus.startsWith('保存失败') ? 'error-text' : 'save-ok'}>{logStatus}</span>}
          </div>
        </section>
      </main>
    </div>
  )
}
