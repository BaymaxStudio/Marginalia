import { NavLink, Link } from 'react-router-dom'
import './AppHeader.css'

const NAV = [
  { to: '/', label: '书库', end: true },
  { to: '/vocabulary', label: '生词本' },
  { to: '/settings', label: '设置' },
]

export default function AppHeader() {
  return (
    <header className="app-header">
      <div className="app-header-in">
        <Link to="/" className="brand" aria-label="Marginalia 书库">
          <span className="brand-mark" aria-hidden="true">M</span>
          <span className="brand-name">Marginalia</span>
        </Link>
        <nav className="app-nav" aria-label="主导航">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}
              className={({ isActive }) => (isActive ? 'active' : '')}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
