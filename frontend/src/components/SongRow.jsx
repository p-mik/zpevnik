import { Link } from 'react-router-dom'
import './ui.css'
import './SongRow.css'

// `href` přebije výchozí cíl (čtečka) — rychlý výběr ve stage módu tak vede
// zase do stage módu, ne ven z něj.
// `current` = právě otevřená píseň (rychlý výběr ve čtečce) — zvýrazní se
// a rychlý výběr na ni po otevření nascrolluje.
export default function SongRow({ song, zpevnikId, href, current = false }) {
  return (
    <li>
      <Link
        className={`song-row${current ? ' song-row-current' : ''}`}
        to={href ?? `/pisne/${song.id}/ctecka${zpevnikId ? `?z=${zpevnikId}` : ''}`}
        aria-current={current ? 'page' : undefined}
      >
        <div className="song-row-inner">
          <span className="code-chip">{String(song.kod).padStart(3, '0')}</span>
          <span className="titles">
            <span className="nazev">{song.nazev}</span>
            {song.interpret && <span className="interpret">{song.interpret}</span>}
          </span>
        </div>
      </Link>
    </li>
  )
}

export function SongList({ children }) {
  return <ul className="song-list">{children}</ul>
}
