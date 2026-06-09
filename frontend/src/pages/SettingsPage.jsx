import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSettings, updateSettings } from '../services/api'
import './SettingsPage.css'

const PROVIDERS = [
  { value: 'claude', label: 'Claude (Anthropic)', desc: '支持 Messages API，推荐 Haiku + Sonnet' },
  { value: 'deepseek', label: 'DeepSeek', desc: 'OpenAI 兼容格式，统一使用 deepseek-chat' },
  { value: 'openai_compat', label: 'OpenAI 兼容', desc: '自定义 base_url + model_name' },
]

export default function SettingsPage() {
  const navigate = useNavigate()
  const [saved, setSaved] = useState(false)
  const [form, setForm] = useState({
    ai_provider: 'claude',
    api_key_claude: '',
    api_key_deepseek: '',
    api_key_openai_compat: '',
    openai_compat_base_url: '',
    openai_compat_model_name: '',
    font_size: 18,
    line_height: 1.8,
    theme: 'light',
    log_level: 'INFO',
  })

  useEffect(() => {
    getSettings().then((s) => setForm((f) => ({ ...f, ...s }))).catch(() => {})
  }, [])

  const handleChange = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const handleSave = async () => {
    try {
      await updateSettings(form)
      document.documentElement.style.setProperty('--font-size', form.font_size + 'px')
      document.documentElement.style.setProperty('--line-height', String(form.line_height))
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) { alert('保存失败: ' + e.message) }
  }

  const apiKeyField = form.ai_provider === 'claude' ? 'api_key_claude'
    : form.ai_provider === 'deepseek' ? 'api_key_deepseek' : 'api_key_openai_compat'

  return (
    <div className="settings-page">
      <header className="settings-header">
        <button className="btn-back" onClick={() => navigate('/')}>← 返回</button>
        <h1>设置</h1>
      </header>

      <div className="settings-body">
        <section>
          <h2>AI 供应商</h2>
          {PROVIDERS.map((p) => (
            <label key={p.value} className={`provider-option ${form.ai_provider === p.value ? 'selected' : ''}`}>
              <input type="radio" name="provider" value={p.value}
                checked={form.ai_provider === p.value}
                onChange={(e) => handleChange('ai_provider', e.target.value)} />
              <div><strong>{p.label}</strong><p>{p.desc}</p></div>
            </label>
          ))}
          <p className="provider-links">
            <span>注册获取 API Key：</span>
            <a href="https://platform.deepseek.com" target="_blank" rel="noopener noreferrer">DeepSeek（推荐国内用户）</a>
            <a href="https://console.anthropic.com" target="_blank" rel="noopener noreferrer">Claude（Anthropic）</a>
            <span>OpenAI 兼容服务 → 请参考你所使用的服务商文档</span>
          </p>
        </section>

        <section>
          <h2>API Key</h2>
          <input type="password" className="input-field"
            placeholder={form.ai_provider === 'openai_compat' ? '输入 API Key...' : `输入 ${PROVIDERS.find(p => p.value === form.ai_provider)?.label} 的 API Key...`}
            value={form[apiKeyField] || ''}
            onChange={(e) => handleChange(apiKeyField, e.target.value)} />
          {form.ai_provider === 'openai_compat' && (
            <>
              <input type="text" className="input-field" placeholder="Base URL (如 https://api.openai.com/v1)"
                value={form.openai_compat_base_url}
                onChange={(e) => handleChange('openai_compat_base_url', e.target.value)} />
              <input type="text" className="input-field" placeholder="Model Name (如 gpt-4o)"
                value={form.openai_compat_model_name}
                onChange={(e) => handleChange('openai_compat_model_name', e.target.value)} />
            </>
          )}
        </section>

        <section>
          <h2>阅读体验</h2>
          <div className="setting-row">
            <label>字体大小</label>
            <div className="range-row">
              <input type="range" min="14" max="28" value={form.font_size}
                onChange={(e) => handleChange('font_size', Number(e.target.value))} />
              <span className="range-val">{form.font_size}px</span>
            </div>
          </div>
          <div className="setting-row">
            <label>行高</label>
            <div className="range-row">
              <input type="range" min="1.4" max="2.4" step="0.1" value={form.line_height}
                onChange={(e) => handleChange('line_height', Number(e.target.value))} />
              <span className="range-val">{form.line_height}</span>
            </div>
          </div>
        </section>

        <section>
          <h2>开发日志</h2>
          <div className="setting-row">
            <label>日志级别</label>
            <select className="input-field" value={form.log_level}
              onChange={(e) => handleChange('log_level', e.target.value)}>
              <option value="INFO">标准（记录操作流水和异常）</option>
              <option value="DEBUG">详细（包含 AI prompt 和内部决策细节）</option>
            </select>
          </div>
        </section>

        <button className="btn-save" onClick={handleSave}>
          {saved ? '✓ 已保存' : '保存设置'}
        </button>
      </div>
    </div>
  )
}
