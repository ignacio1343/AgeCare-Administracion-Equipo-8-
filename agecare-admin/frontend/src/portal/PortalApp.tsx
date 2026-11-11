// Portal web responsivo (computador y celular) para representantes, residentes y cuidadores.
import { useEffect, useState, type ReactNode } from 'react'
import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router'
import { Cambiar, Ingresar, Olvide, Registro } from './Acceso'
import { PortalAuthProvider, usePortal } from './auth'
import { papi, type Notificacion, type Vista } from './api'
import Cuidador from './Cuidador'
import { PasarelaSimulada, ResultadoPago } from './Pagos'
import { Contratar, EstadoResidente, InicioRepresentante, NuevoResidente } from './Representante'
import { Ayuda, InicioResidente } from './Residente'
import { MisSolicitudes, VerSolicitud } from './Solicitudes'
import './portal.css'

const ETIQUETA: Record<Vista, string> = { representante: 'Representante', residente: 'Residente', cuidador: 'Cuidador' }
const INICIO: Record<Vista, string> = { representante: '/portal/representante', residente: '/portal/residente', cuidador: '/portal/cuidador' }

export function Marca({ claro = false }: { claro?: boolean }) {
  return (
    <Link to="/portal" className={`p-marca${claro ? ' claro' : ''}`}>
      <span className="p-logo">A</span><span><b>AgeCare</b><small>Portal de familias</small></span>
    </Link>
  )
}

export function Cargando() { return <div className="p-cargando" role="status">Cargando…</div> }

function ConSesion({ vista, children }: { vista?: Vista; children: ReactNode }) {
  const { me, cargando } = usePortal()
  const loc = useLocation()
  if (cargando) return <Cargando />
  if (!me) return <Navigate to="/portal/ingresar" replace state={{ desde: loc.pathname + loc.search }} />
  if (me.debe_cambiar_password && loc.pathname !== '/portal/cambiar-clave') return <Navigate to="/portal/cambiar-clave" replace />
  if (vista && !me.vistas.includes(vista)) return <Navigate to="/portal" replace />
  return <>{children}</>
}

function Inicio() {
  const { me, cargando } = usePortal()
  if (cargando) return <Cargando />
  if (!me) return <Navigate to="/portal/ingresar" replace />
  if (me.debe_cambiar_password) return <Navigate to="/portal/cambiar-clave" replace />
  return <Navigate to={INICIO[me.vistas[0]] ?? '/portal/ingresar'} replace />
}

function Campana() {
  const nav = useNavigate()
  const [abierta, setAbierta] = useState(false)
  const [items, setItems] = useState<Notificacion[]>([])
  const [sinLeer, setSinLeer] = useState(0)
  const cargar = () => papi<{ sin_leer: number; items: Notificacion[] }>('/notificaciones')
    .then(r => { setItems(r.items); setSinLeer(r.sin_leer) }).catch(() => {})
  useEffect(() => {
    cargar()
    const t = setInterval(cargar, 30_000)  // los avisos de riesgo aparecen sin recargar la página
    return () => clearInterval(t)
  }, [])
  const abrir = async () => {
    setAbierta(a => !a)
    if (!abierta && sinLeer) {
      const r = await papi<{ sin_leer: number; items: Notificacion[] }>('/notificaciones/leer', { method: 'POST' })
      setSinLeer(r.sin_leer)
    }
  }
  return (
    <div className="p-campana">
      <button className="p-icono" onClick={abrir} aria-label={`Avisos${sinLeer ? `: ${sinLeer} sin leer` : ''}`}>
        🔔{sinLeer > 0 && <span className="p-badge">{sinLeer}</span>}
      </button>
      {abierta && (
        <div className="p-avisos" role="dialog" aria-label="Avisos">
          <div className="p-avisos-head"><b>Avisos</b><button className="p-link" onClick={() => setAbierta(false)}>Cerrar</button></div>
          {items.length === 0 && <p className="p-muted">No tienes avisos.</p>}
          {items.map(n => (
            <div key={n.id_notificacion} className={`p-aviso ${n.tipo}${n.leida ? '' : ' nueva'}${n.enlace ? ' con-enlace' : ''}`}
                 role={n.enlace ? 'link' : undefined} tabIndex={n.enlace ? 0 : undefined}
                 onClick={() => { if (n.enlace) { setAbierta(false); nav(n.enlace) } }}
                 onKeyDown={e => { if (n.enlace && e.key === 'Enter') { setAbierta(false); nav(n.enlace) } }}>
              <b>{n.titulo}</b><p>{n.cuerpo}</p><small>{new Date(n.fecha_creacion).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })}{n.enlace ? ' · Ver →' : ''}</small>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Marco() {
  const { me, salir } = usePortal()
  const nav = useNavigate()
  if (!me) return null
  const cerrar = async () => { await salir(); nav('/portal/ingresar') }
  return (
    <div className="p-shell">
      <header className="p-header">
        <Marca />
        {me.vistas.length > 1 && (
          <nav className="p-vistas" aria-label="Cambiar de vista">
            {me.vistas.map(v => <NavLink key={v} to={INICIO[v]}>{ETIQUETA[v]}</NavLink>)}
          </nav>
        )}
        <div className="p-spacer" />
        <NavLink to="/portal/solicitudes" className="p-icono p-icono-link" title="Mis solicitudes" aria-label="Mis solicitudes">📨</NavLink>
        <Campana />
        <div className="p-quien"><b>{me.nombres ?? me.nombre}</b><small>{me.vistas.map(v => ETIQUETA[v]).join(' · ')}</small></div>
        <button className="p-btn ghost sm" onClick={cerrar}>Salir</button>
      </header>
      <main className="p-main"><Outlet /></main>
      <footer className="p-footer">
        <Link to="/portal/ayuda">¿Necesitas ayuda?</Link> · <Link to="/portal/solicitudes">Mis solicitudes</Link> · AgeCare · Wellq Co
      </footer>
    </div>
  )
}

export default function PortalApp() {
  return (
    <PortalAuthProvider>
      <Routes>
        <Route index element={<Inicio />} />
        <Route path="ingresar" element={<Ingresar />} />
        <Route path="registro" element={<Registro />} />
        <Route path="olvide" element={<Olvide />} />
        <Route path="pago/resultado" element={<ResultadoPago />} />
        <Route element={<ConSesion><Marco /></ConSesion>}>
          <Route path="cambiar-clave" element={<Cambiar />} />
          <Route path="ayuda" element={<Ayuda />} />
          <Route path="solicitudes" element={<MisSolicitudes />} />
          <Route path="solicitudes/:numero" element={<VerSolicitud />} />
          <Route path="representante" element={<ConSesion vista="representante"><InicioRepresentante /></ConSesion>} />
          <Route path="representante/contratar" element={<ConSesion vista="representante"><Contratar /></ConSesion>} />
          <Route path="representante/plan/:id/residente" element={<ConSesion vista="representante"><NuevoResidente /></ConSesion>} />
          <Route path="representante/residente/:id" element={<ConSesion vista="representante"><EstadoResidente /></ConSesion>} />
          <Route path="pago/simulado" element={<ConSesion vista="representante"><PasarelaSimulada /></ConSesion>} />
          <Route path="residente" element={<ConSesion vista="residente"><InicioResidente /></ConSesion>} />
          <Route path="cuidador" element={<ConSesion vista="cuidador"><Cuidador /></ConSesion>} />
        </Route>
        <Route path="*" element={<Navigate to="/portal" replace />} />
      </Routes>
    </PortalAuthProvider>
  )
}
