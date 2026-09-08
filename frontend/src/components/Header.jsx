import { useNavigate, Link, NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import './Header.css'

export default function Header() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    try {
      await logout()
    } finally {
      navigate('/prihlaseni', { replace: true })
    }
  }

  return (
    <header className="header-frame">
      <div className="header-text">
        <Link to="/pisne">
          <h1>Zpěvník</h1>
        </Link>
      </div>
      <nav className="header-nav" aria-label="Hlavní navigace">
        <NavItem to="/pisne">Písně</NavItem>
        <NavItem to="/slozky">Zpěvníky</NavItem>
        <NavItem to="/setlisty">Setlisty</NavItem>
        <button type="button" className="nav-item nav-ghost" onClick={handleLogout}>
          Odhlásit
        </button>
      </nav>
    </header>
  )
}

function NavItem({ to, children }) {
  // Aktivní sekce je zvýrazněná, ostatní neutrální — barva teď nese "kde
  // jsem", ne identitu sekce (viz zpětná vazba po prvním prokliknutí appky).
  return (
    <NavLink to={to} className={({ isActive }) => `nav-item${isActive ? ' nav-active' : ''}`}>
      {children}
    </NavLink>
  )
}
