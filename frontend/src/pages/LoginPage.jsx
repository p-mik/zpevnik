import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import '../components/ui.css'
import './LoginPage.css'

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) {
    const from = location.state?.from?.pathname || '/pisne'
    return <Navigate to={from} replace />
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username, password)
      const from = location.state?.from?.pathname || '/pisne'
      navigate(from, { replace: true })
    } catch (err) {
      setError(err.detail || 'Přihlášení se nepovedlo.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="panel login-panel" onSubmit={handleSubmit}>
        <h1>Zpěvník</h1>

        <div className="field">
          <label className="field-label" htmlFor="username">
            Uživatelské jméno
          </label>
          <input
            id="username"
            className="field-input"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        <div className="field">
          <label className="field-label" htmlFor="password">
            Heslo
          </label>
          <input
            id="password"
            className="field-input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {error && <div className="toast-error">{error}</div>}

        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Přihlašuji…' : 'Přihlásit se'}
        </button>
      </form>
    </div>
  )
}
