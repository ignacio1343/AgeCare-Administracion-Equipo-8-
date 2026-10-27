import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, session, tryRefresh, type Perfil } from './api'

interface AuthState {
  perfil: Perfil | null
  cargando: boolean
  login: (email: string, password: string, codigo_otp?: string) => Promise<void>
  logout: () => Promise<void>
  recargar: () => Promise<void>
  puede: (modulo: string, nivel?: 'lectura' | 'escritura') => boolean
}

const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const [cargando, setCargando] = useState(true)

  const recargar = useCallback(async () => { setPerfil(await api<Perfil>('/auth/me')) }, [])

  useEffect(() => {
    session.onLost(() => setPerfil(null))
    ;(async () => {
      // Al abrir la consola se intenta recuperar la sesión con la cookie HttpOnly del refresh token
      if (session.puedeRecuperar() && (await tryRefresh())) {
        try { await recargar() } catch { session.clear() }
      }
      setCargando(false)
    })()
  }, [recargar])

  const login = async (email: string, password: string, codigo_otp?: string) => {
    const r = await api<{ access_token: string; staff: Perfil }>('/auth/login', {
      method: 'POST', body: { email, password, codigo_otp: codigo_otp || null },
    })
    session.set(r.access_token)
    setPerfil(r.staff)
  }

  const logout = async () => {
    try { await api('/auth/logout', { method: 'POST', headers: { 'X-ACA-Refresh': '1' } }) } catch { /* sesión ya inválida */ }
    session.clear()
    setPerfil(null)
  }

  // "a|b" = basta con permiso sobre cualquiera de los módulos
  const puede = (modulo: string, nivel: 'lectura' | 'escritura' = 'lectura'): boolean => {
    if (modulo.includes('|')) return modulo.split('|').some(m => puede(m, nivel))
    const p = perfil?.permisos[modulo]
    return nivel === 'lectura' ? !!p : p === 'escritura'
  }

  return <Ctx.Provider value={{ perfil, cargando, login, logout, recargar, puede }}>{children}</Ctx.Provider>
}

export function useAuth() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useAuth fuera de AuthProvider')
  return c
}
