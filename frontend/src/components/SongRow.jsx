import { Link } from 'react-router-dom'
import './ui.css'
import './SongRow.css'

export default function SongRow({ song }) {
  return (
    <li>
      <Link className="song-row" to={`/pisne/${song.id}`}>
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
