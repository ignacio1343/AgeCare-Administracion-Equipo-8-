import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { papi, portalRefresh, portalSession, type Me } from './api'

interface PortalAuth {
  me: Me | null
  cargando: boolean
  entrar: (usuario: string, password: string) => Promise<Me>
  conTokens: (access: string, me: Me) => void
  salir: () => Promise<void>
  recargar: () => Promise<void>
}

const Ctx = createContext<PortalAuth | null>(null)

export function PortalAuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [cargando, setCargando] = useState(true)
  const recargar = useCallback(async () => { setMe(await papi<Me>('/auth/me')) }, [])

  useEffect(() => {
    portalSession.onLost(() => setMe(null))
    ;(async () => {
      if (portalSession.puedeRecuperar() && (await portalRefresh())) {
        try { await recargar() } catch { portalSession.clear() }
      }
      setCargando(false)
    })()
  }, [recargar])

  const conTokens = (access: string, m: Me) => { portalSession.set(access); setMe(m) }
  const entrar = async (usuario: string, password: string) => {
    const r = await papi<{ access_token: string; usuario: Me }>('/auth/login', { method: 'POST', body: { usuario, password } })
    conTokens(r.access_token, r.usuario)
    return r.usuario
  }
  const salir = async () => {
    try { await papi('/auth/logout', { method: 'POST', headers: { 'X-ACA-Refresh': '1' } }) } catch { /* ya inválida */ }
    portalSession.clear()
    setMe(null)
  }
  return <Ctx.Provider value={{ me, cargando, entrar, conTokens, salir, recargar }}>{children}</Ctx.Provider>
}

export function usePortal() {
  const c = useContext(Ctx)
  if (!c) throw new Error('usePortal fuera de PortalAuthProvider')
  return c
}
