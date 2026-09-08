import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import Header from './Header'
import LoadingState from './LoadingState'

export default function ProtectedLayout() {
  const { user } = useAuth()
  const location = useLocation()

  if (user === undefined) {
    // Ještě nevíme, jestli je session platná — bílá stránka by vypadala jako
    // pád appky, tohle ne.
    return <LoadingState label="Ověřuji přihlášení…" />
  }

  if (user === null) {
    return <Navigate to="/prihlaseni" replace state={{ from: location }} />
  }

  return (
    <>
      <Header />
      <main className="app-main">
        <Outlet />
      </main>
    </>
  )
}
