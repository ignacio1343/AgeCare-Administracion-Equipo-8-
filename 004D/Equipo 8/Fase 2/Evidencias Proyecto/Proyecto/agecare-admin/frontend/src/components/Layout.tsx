import { NavLink, Outlet, useLocation } from 'react-router'
import { useAuth } from '../auth'

// Menú lateral: un ítem por módulo del diagrama de casos de uso.
// Solo se muestran los módulos a los que el rol tiene acceso (permisos de /auth/me).
export const MODULOS: { grupo: string; items: { to: string; label: string; ico: string; permiso: string; listo: boolean; sprint?: string }[] }[] = [
  {
    grupo: 'Operación', items: [
      { to: '/soporte', label: 'Soporte (tickets)', ico: '🎫', permiso: 'soporte', listo: true },
      { to: '/usuarios', label: 'Usuarios de la app', ico: '👥', permiso: 'usuarios', listo: true },
      { to: '/estado', label: 'Estado operativo', ico: '🖥️', permiso: 'operacion', listo: true },
      { to: '/whatsapp', label: 'Avisos WhatsApp', ico: '💬', permiso: 'operacion', listo: true },
      { to: '/contenidos', label: 'Contenidos y productos', ico: '📰', permiso: 'contenido|marketplace', listo: true },
      { to: '/moderacion', label: 'Moderación', ico: '🛡️', permiso: 'moderacion', listo: true },
    ],
  },
  {
    grupo: 'Negocio', items: [
      { to: '/dashboards', label: 'Dashboards', ico: '📈', permiso: 'metricas', listo: true },
      { to: '/planes', label: 'Planes y suscripciones', ico: '💳', permiso: 'comercial', listo: true },
    ],
  },
  {
    grupo: 'Sistema', items: [
      { to: '/configuracion', label: 'Configuración y legales', ico: '⚙️', permiso: 'configuracion', listo: true },
      { to: '/staff', label: 'Staff y roles', ico: '🔑', permiso: 'staff', listo: true },
      { to: '/auditoria', label: 'Auditoría', ico: '📜', permiso: 'staff', listo: true },
    ],
  },
]

const TITULOS: Record<string, [string, string]> = {
  '/soporte': ['Soporte', 'Operación · Cola de tickets e indicadores'],
  '/staff': ['Staff y roles', 'Sistema · Cuentas internas y permisos'],
  '/auditoria': ['Auditoría', 'Sistema · Bitácora inmutable de acciones'],
  '/perfil': ['Mi cuenta', 'Seguridad · Segundo factor'],
  '/usuarios': ['Usuarios de la app', 'Operación · Búsqueda, cuentas y círculos de cuidado'],
  '/estado': ['Estado operativo', 'Operación · Componentes, procesos críticos e incidentes'],
  '/whatsapp': ['Avisos WhatsApp', 'Operación · Avisos de salud al familiar del paciente'],
  '/contenidos': ['Contenidos y productos', 'Operación · Feed curado, marketplace y cuidadoras'],
  '/moderacion': ['Moderación', 'Operación · Contenido reportado por la comunidad'],
  '/dashboards': ['Dashboards', 'Negocio · Métricas comerciales, embudo, perfiles y adopción'],
  '/planes': ['Planes y suscripciones', 'Negocio · Planes, cuentas, pagos y reembolsos'],
  '/configuracion': ['Configuración y legales', 'Sistema · Parámetros, umbrales y documentos legales'],
}

export default function Layout() {
  const { perfil, logout, puede } = useAuth()
  const loc = useLocation()
  const base = '/' + (loc.pathname.split('/')[1] ?? '')
  const item = MODULOS.flatMap(g => g.items).find(i => i.to === base)
  const [titulo, crumb] = TITULOS[base] ?? (item ? [item.label, `Módulo previsto para ${item.sprint}`] : ['Consola', ''])
  const iniciales = perfil?.nombre_completo.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase()

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-mark">A</div>
          <div><div className="logo-name">AgeCare</div><div className="logo-sub">Consola de administración</div></div>
        </div>
        <nav className="nav" aria-label="Módulos">
          {MODULOS.map(g => {
            const visibles = g.items.filter(i => puede(i.permiso))
            if (!visibles.length) return null
            return (
              <div key={g.grupo}>
                <div className="nav-group">{g.grupo}</div>
                {visibles.map(i => (
                  <NavLink key={i.to} to={i.to} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
                    <span className="ico" aria-hidden>{i.ico}</span>{i.label}
                    {!i.listo && <span className="soon">{i.sprint?.replace('Sprint ', 'S')}</span>}
                  </NavLink>
                ))}
              </div>
            )
          })}
        </nav>
        <NavLink to="/perfil" className="sidebar-foot">
          <div className="sf-avatar">{iniciales}</div>
          <div><div className="sf-name">{perfil?.nombre_completo}</div><div className="sf-role">{perfil?.rol_nombre}</div></div>
        </NavLink>
      </aside>
      <div className="main">
        <header className="topbar">
          <div><div className="tb-title">{titulo}</div><div className="tb-crumb">{crumb}</div></div>
          <div className="tb-spacer" />
          {perfil?.configurar_mfa && <NavLink to="/perfil" className="chip warn">▲ Configura tu segundo factor</NavLink>}
          <button className="btn ghost sm" onClick={logout}>Cerrar sesión</button>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  )
}
