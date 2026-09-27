import { Link } from 'react-router-dom'

// 未配置 API Key 的错误给出设置入口，其他错误原样显示原因
export default function ErrorMessage({ message }) {
  const needsKey = /API Key/i.test(message)
  return (
    <p className="error-text" role="alert">
      {message}
      {needsKey && <> <Link to="/settings">前往设置</Link></>}
    </p>
  )
}
