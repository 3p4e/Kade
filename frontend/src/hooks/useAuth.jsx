import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api.js'

const Ctx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const t = api.getToken()
    if (!t) { setLoading(false); return }
    api.me()
      .then(setUser)
      .catch(() => api.setToken(''))
      .finally(() => setLoading(false))
  }, [])

  async function login(email, password) {
    const res = await api.login(email, password)
    api.setToken(res.access_token)
    const me = await api.me()
    setUser(me)
    return me
  }

  function logout() {
    api.setToken('')
    setUser(null)
  }

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
