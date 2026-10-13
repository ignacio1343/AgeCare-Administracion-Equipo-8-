import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Layout, { MODULOS } from './components/Layout'
import { Cargando } from './components/ui'
import Activar from './pages/Activar'
import Auditoria from './pages/Auditoria'
import Login from './pages/Login'
import Perfil from './pages/Perfil'
import Proximamente from './pages/Proximamente'
import Staff from './pages/Staff'

// Ruta protegida: exige sesión y, si se indica, permiso sobre un módulo
function Protegida({ permiso, nivel = 'lectura', children }: { permiso?: string; nivel?: 'lectura' | 'escritura'; children: ReactNode }) {
  const { perfil, cargando, puede } = useAuth()
  const loc = useLocation()
  if (cargando) return <Cargando />
  if (!perfil) return <Navigate to="/login" replace state={{ desde: loc.pathname }} />
  if (permiso && !puede(permiso, nivel)) return <SinPermiso />
  return <>{children}</>
}

function SinPermiso() {
  return <div className="placeholder-box"><div className="ph-ico">🔒</div><b>Tu rol no tiene acceso a este módulo.</b><p>Si lo necesitas, pide a un administrador que revise tu rol.</p></div>
}

function Inicio() {
  const { puede } = useAuth()
  const primero = MODULOS.flatMap(g => g.items).find(i => i.listo && puede(i.permiso))
  return <Navigate to={primero?.to ?? '/perfil'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/activar" element={<Activar />} />
      <Route element={<Protegida><Layout /></Protegida>}>
        <Route index element={<Inicio />} />
        <Route path="staff" element={<Protegida permiso="staff"><Staff /></Protegida>} />
        <Route path="auditoria" element={<Protegida permiso="staff"><Auditoria /></Protegida>} />
        <Route path="perfil" element={<Perfil />} />
        {MODULOS.flatMap(g => g.items).filter(i => !i.listo).map(i => (
          <Route key={i.to} path={i.to.slice(1)} element={<Protegida permiso={i.permiso}><Proximamente modulo={i} /></Protegida>} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
