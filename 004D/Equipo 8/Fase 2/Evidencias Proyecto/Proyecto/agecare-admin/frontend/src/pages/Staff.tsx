import { useEffect, useState, type FormEvent } from 'react'
import { api, type Page, type Rol, type Staff as S } from '../api'
import { useAuth } from '../auth'
import { Card, Cargando, ErrorBox, fechaHora, Paginacion, ROLES } from '../components/ui'

const ESTADO_STAFF: Record<string, string> = { pendiente: 'warn', activo: 'ok', inactivo: 'muted' }

// CU03 · Gestionar cuentas y roles del staff
export default function Staff() {
  const { perfil } = useAuth()
  const [data, setData] = useState<Page<S> | null>(null)
  const [roles, setRoles] = useState<Rol[]>([])
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [nuevo, setNuevo] = useState({ nombre_completo: '', email: '', codigo_rol: 'soporte' })
  const [enlace, setEnlace] = useState<{ email: string; url: string } | null>(null)
  const [abierto, setAbierto] = useState(false)

  const cargar = () => api<Page<S>>('/staff', { query: { q, page, page_size: 20 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [page]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api<Rol[]>('/staff/roles').then(setRoles).catch(() => {}) }, [])

  const crear = async (e: FormEvent) => {
    e.preventDefault(); setError(null)
    try {
      const r = await api<{ staff: S; enlace_activacion: string }>('/staff', { method: 'POST', body: nuevo })
      setEnlace({ email: r.staff.email, url: r.enlace_activacion })
      setNuevo({ nombre_completo: '', email: '', codigo_rol: 'soporte' }); setAbierto(false); cargar()
    } catch (err) { setError(err) }
  }
  const cambiar = async (s: S, body: Record<string, unknown>) => {
    setError(null)
    try { await api(`/staff/${s.id_staff}`, { method: 'PATCH', body }); cargar() } catch (err) { setError(err) }
  }
  const reenviar = async (s: S) => {
    try { const r = await api<{ enlace_activacion: string }>(`/staff/${s.id_staff}/invitacion`, { method: 'POST' }); setEnlace({ email: s.email, url: r.enlace_activacion }) }
    catch (err) { setError(err) }
  }

  return (
    <>
      {enlace && (
        <div className="alert ok">
          <div><b>Invitación creada para {enlace.email}.</b> El envío por correo está simulado en esta versión: comparte este enlace
            (válido 24 h) para que la persona defina su contraseña.</div>
          <div className="copy"><code>{enlace.url}</code><button className="btn ghost sm" onClick={() => navigator.clipboard?.writeText(enlace.url)}>Copiar</button>
            <button className="btn link sm" onClick={() => setEnlace(null)}>Ocultar</button></div>
        </div>
      )}
      <ErrorBox error={error} />
      <Card title="Cuentas del staff" sub="Las cuentas nuevas quedan pendientes hasta que la persona activa su enlace"
        actions={<button className="btn primary sm" onClick={() => setAbierto(!abierto)}>{abierto ? 'Cancelar' : '+ Nueva cuenta'}</button>}>
        {abierto && (
          <form className="form inline-form" onSubmit={crear}>
            <label>Nombre completo<input value={nuevo.nombre_completo} onChange={e => setNuevo({ ...nuevo, nombre_completo: e.target.value })} required minLength={2} /></label>
            <label>Correo corporativo<input type="email" value={nuevo.email} onChange={e => setNuevo({ ...nuevo, email: e.target.value })} required placeholder="nombre@wellq.co.uk" /></label>
            <label>Rol<select value={nuevo.codigo_rol} onChange={e => setNuevo({ ...nuevo, codigo_rol: e.target.value })}>
              {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            <div className="actions"><button className="btn primary">Crear e invitar</button></div>
          </form>
        )}
        <form className="filters" onSubmit={e => { e.preventDefault(); setPage(1); cargar() }}>
          <div className="search"><input placeholder="Buscar por nombre o correo" value={q} onChange={e => setQ(e.target.value)} aria-label="Buscar" /></div>
        </form>
        {!data ? <Cargando /> : (
          <>
            <div className="table-wrap"><table className="data">
              <thead><tr><th>Nombre</th><th>Rol</th><th>Estado</th><th>2FA</th><th>Último acceso</th><th></th></tr></thead>
              <tbody>
                {data.items.map(s => {
                  const yo = s.id_staff === perfil?.id_staff
                  return (
                    <tr key={s.id_staff}>
                      <td><div className="strong">{s.nombre_completo}{yo && <span className="muted"> (tú)</span>}</div><div className="sub">{s.email}</div></td>
                      <td><select value={s.codigo_rol} onChange={e => cambiar(s, { codigo_rol: e.target.value })} aria-label={`Rol de ${s.nombre_completo}`}>
                        {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td>
                      <td><span className={`chip ${ESTADO_STAFF[s.estado]}`}>{s.estado}</span></td>
                      <td>{s.mfa_habilitado ? <span className="chip ok">✔ Activo</span> : s.mfa_requerido ? <span className="chip warn">Pendiente</span> : <span className="muted">No</span>}</td>
                      <td className="nowrap">{fechaHora(s.ultimo_acceso)}</td>
                      <td className="right nowrap">
                        {s.estado === 'pendiente' && <button className="btn ghost sm" onClick={() => reenviar(s)}>Reenviar invitación</button>}
                        {s.estado === 'activo' && !yo && <button className="btn ghost sm danger" onClick={() => cambiar(s, { estado: 'inactivo' })}>Desactivar</button>}
                        {s.estado === 'inactivo' && <button className="btn ghost sm" onClick={() => cambiar(s, { estado: 'activo' })}>Reactivar</button>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table></div>
            <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
          </>
        )}
      </Card>
      <Card title="Matriz de permisos por rol" sub="L = lectura · E = lectura y escritura · — = sin acceso">
        <div className="table-wrap"><table className="data matrix">
          <thead><tr><th>Módulo</th>{roles.map(r => <th key={r.codigo_rol}>{r.nombre}</th>)}</tr></thead>
          <tbody>
            {[...new Set(roles.flatMap(r => r.permisos.map(p => p.modulo)))].sort().map(m => (
              <tr key={m}><td className="strong">{m}</td>{roles.map(r => {
                const n = r.permisos.find(p => p.modulo === m)?.nivel_acceso
                return <td key={r.codigo_rol} className={n ? `lvl ${n}` : 'lvl none'}>{n === 'escritura' ? 'E' : n === 'lectura' ? 'L' : '—'}</td>
              })}</tr>
            ))}
          </tbody>
        </table></div>
      </Card>
    </>
  )
}
