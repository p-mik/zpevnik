import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import './NotFoundPage.css'

export default function NotFoundPage() {
  return (
    <div className="not-found-page">
      <EmptyState title="Stránka nenalezena" description="Tahle adresa neexistuje." />
      <p className="back-link">
        <Link to="/pisne">Zpět na seznam písní</Link>
      </p>
    </div>
  )
}
