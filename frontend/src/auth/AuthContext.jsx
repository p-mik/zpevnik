import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api, registerForbiddenHandler } from '../api/client'

const AuthContext = createContext(null)

// `undefined` = ještě nevíme (načítá se), `null` = nepřihlášený, objekt = přihlášený.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined)
  const userRef = useRef(user)
  userRef.current = user

  const refreshMe = useCallback(async () => {
    const data = await api.get('/api/auth/me/')
    setUser(data.authenticated ? data : null)
    return data
  }, [])

  useEffect(() => {
    refreshMe().catch(() => setUser(null))
  }, [refreshMe])

  useEffect(() => {
    // Google OAuth appku nahradí bez přepisu — tohle je jediné místo, kde se
    // API dozví "možná vypršela session", nezávisle na tom, jak se přihlašuje.
    registerForbiddenHandler(async () => {
      if (userRef.current == null) return // ani jsme si nemysleli, že jsme přihlášení
      try {
        const data = await api.get('/api/auth/me/')
        if (!data.authenticated) setUser(null)
      } catch {
        setUser(null)
      }
    })
  }, [])

  const login = useCallback(async (username, password) => {
    const data = await api.post('/api/auth/login/', { username, password })
    setUser(data)
    return data
  }, [])

  const logout = useCallback(async () => {
    await api.post('/api/auth/logout/')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth musí být uvnitř AuthProvider')
  return ctx
}
