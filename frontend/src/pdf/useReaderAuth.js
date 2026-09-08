import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

// Čtečka se chová jinak než běžné chráněné stránky (ProtectedLayout):
// jakmile jednou prošla branou (uživatel byl přihlášený), vypršelá session
// uprostřed čtení appku nesmí přesměrovat na přihlášení a smazat tak
// rozečtené noty — PDF je navíc stejně už stažené v prohlížeči, takže ho
// není proč schovávat. Místo přesměrování se jen nastaví `sessionLost`,
// stránka si sama zobrazí neintruzivní upozornění a obsah nechá být.
export function useReaderAuth() {
  const { user } = useAuth()
  const location = useLocation()
  const enteredRef = useRef(false)
  const [sessionLost, setSessionLost] = useState(false)

  if (user) enteredRef.current = true

  useEffect(() => {
    if (enteredRef.current && user === null) setSessionLost(true)
  }, [user])

  if (!enteredRef.current) {
    if (user === undefined) return { status: 'loading' }
    return { status: 'redirect', from: location }
  }

  return { status: 'ready', sessionLost }
}
