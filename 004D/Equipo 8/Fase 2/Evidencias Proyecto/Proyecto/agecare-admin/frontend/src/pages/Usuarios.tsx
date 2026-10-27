import { useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { useAuth } from '../auth'
import { Card, Cargando, Chip, ErrorBox, fecha, fechaHora, hace, Paginacion, PERFILES } from '../components/ui'

interface Usuario {
  id_usuario: number; nombre: string; email: string; estado_cuenta: string; perfiles: string[]; pacientes: string[]
  fecha_registro: string; ultimo_acceso: string | null
}
interface Membresia { id_paciente: number; paciente: string; rol_en_circulo: string; estado: string; fecha_invitacion: string; fecha_aceptacion: string | null }
interface Detalle extends Usuario {
  membresias: Membresia[]; tickets_total: number; tickets_abiertos: number
  telefono: string | null; whatsapp_habilitado: boolean; whatsapp_verificado: string | null
}

// CU32 Buscar usuarios y pacientes · CU33 Desactivar/reactivar cuenta · CU34 Reenviar invitación al círculo de cuidado
export default function Usuarios() {
  const { puede } = useAuth()
  const escribe = puede('usuarios', 'escritura')
  const [data, setData] = useState<Page<Usuario> | null>(null)
  const [f, setF] = useState({ q: '', perfil: '', estado: '', page: 1 })
  const [q, setQ] = useState('')
  const [sel, setSel] = useState<Detalle | null>(null)
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [aviso, setAviso] = useState('')

  const cargar = () => api<Page<Usuario>>('/usuarios', { query: { ...f, page_size: 15 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [f]) // eslint-disable-line react-hooks/exhaustive-deps
  const abrir = (id: number, limpiar = true) => {
    if (limpiar) setAviso('')
    setMotivo(''); api<Detalle>(`/usuarios/${id}`).then(setSel).catch(setError)
  }

  const cambiarEstado = async () => {
    if (!sel) return
    setError(null)
    const nuevo = sel.estado_cuenta === 'activa' ? 'desactivada' : 'activa'
    try {
      await api(`/usuarios/${sel.id_usuario}/estado`, { method: 'PATCH', body: { estado_cuenta: nuevo, motivo } })
      setAviso(nuevo === 'activa' ? 'Cuenta reactivada.' : 'Cuenta desactivada: la persona ya no puede iniciar sesión en la app.')
      abrir(sel.id_usuario, false); cargar()
    } catch (e) { setError(e) }
  }
  const reinvitar = async (m: Membresia) => {
    if (!sel) return
    setError(null)
    try {
      await api(`/usuarios/${sel.id_usuario}/membresias/${m.id_paciente}/invitacion`, { method: 'POST' })
      setAviso(`Invitación al círculo de ${m.paciente} reenviada a ${sel.email} (envío simulado).`)
      abrir(sel.id_usuario, false)
    } catch (e) { setError(e) }
  }

  return (
    <div className="grid split">
      <Card title="Usuarios de la app" sub="CU32 · busca por nombre, correo o nombre del paciente">
        <div className="filters">
          <form className="search" onSubmit={e => { e.preventDefault(); setF({ ...f, q: q.trim(), page: 1 }) }}>
            <input placeholder="Buscar usuario o paciente" value={q} onChange={e => setQ(e.target.value)} aria-label="Buscar" />
          </form>
          <select value={f.perfil} onChange={e => setF({ ...f, perfil: e.target.value, page: 1 })} aria-label="Perfil">
            <option value="">Perfil</option>{Object.entries(PERFILES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={f.estado} onChange={e => setF({ ...f, estado: e.target.value, page: 1 })} aria-label="Estado">
            <option value="">Estado</option><option value="activa">Activa</option><option value="desactivada">Desactivada</option>
          </select>
        </div>
        {!data ? <Cargando /> : (
          <>
            <div className="table-wrap"><table className="data clickable">
              <thead><tr><th>Usuario</th><th>Perfiles</th><th>Pacientes</th><th>Estado</th><th>Último acceso</th></tr></thead>
              <tbody>
                {data.items.map(u => (
                  <tr key={u.id_usuario} className={sel?.id_usuario === u.id_usuario ? 'sel' : ''} tabIndex={0}
                    onClick={() => abrir(u.id_usuario)} onKeyDown={e => e.key === 'Enter' && abrir(u.id_usuario)}>
                    <td><div className="strong">{u.nombre}</div><div className="sub">{u.email}</div></td>
                    <td>{u.perfiles.map(p => PERFILES[p] ?? p).join(', ')}</td>
                    <td>{u.pacientes.join(', ') || <span className="muted">—</span>}</td>
                    <td><Chip estado={u.estado_cuenta} /></td>
                    <td className="nowrap">{hace(u.ultimo_acceso)}</td>
                  </tr>
                ))}
              </tbody>
            </table>{!data.items.length && <p className="empty">Sin coincidencias.</p>}</div>
            <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={p => setF({ ...f, page: p })} />
          </>
        )}
      </Card>

      <Card title={sel ? sel.nombre : 'Ficha del usuario'} sub={sel ? sel.email : 'Selecciona una fila para ver el detalle'}>
        <ErrorBox error={error} />
        {aviso && <div className="alert ok">{aviso}</div>}
        {!sel ? <p className="muted">Aquí verás perfiles, círculos de cuidado y acciones de soporte.</p> : (
          <>
            <dl className="kv">
              <dt>Estado</dt><dd><Chip estado={sel.estado_cuenta} /></dd>
              <dt>Perfiles</dt><dd>{sel.perfiles.map(p => PERFILES[p] ?? p).join(', ')}</dd>
              <dt>Registro</dt><dd>{fecha(sel.fecha_registro)}</dd>
              <dt>Último acceso</dt><dd>{fechaHora(sel.ultimo_acceso)}</dd>
              <dt>Tickets</dt><dd>{sel.tickets_total} en total · {sel.tickets_abiertos} abiertos</dd>
            </dl>
            <h4 className="card-title" style={{ margin: '16px 0 8px' }}>Círculos de cuidado</h4>
            {!sel.membresias.length ? <p className="muted">No pertenece a ningún círculo.</p> : (
              <div className="table-wrap"><table className="data">
                <thead><tr><th>Paciente</th><th>Rol</th><th>Estado</th><th></th></tr></thead>
                <tbody>{sel.membresias.map(m => (
                  <tr key={m.id_paciente}>
                    <td className="strong">{m.paciente}</td><td>{PERFILES[m.rol_en_circulo] ?? m.rol_en_circulo}</td>
                    <td><Chip estado={m.estado} /><div className="sub">{m.estado === 'invitado' ? `invitado ${hace(m.fecha_invitacion)}` : fecha(m.fecha_aceptacion)}</div></td>
                    <td className="right">{escribe && m.estado === 'invitado' && <button className="btn ghost sm" onClick={() => reinvitar(m)}>Reenviar invitación</button>}</td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
            {sel.membresias.some(m => m.rol_en_circulo === 'familiar') && (
              <AvisosWhatsapp u={sel} escribe={escribe} onGuardado={d => { setSel(d); setAviso('Preferencias de WhatsApp guardadas.') }} />
            )}
            {escribe && (
              <div className="stack">
                <label className="stack">Motivo (queda en la auditoría)
                  <input value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Ej.: solicitud del titular por correo" /></label>
                <div className="panel-actions">
                  <button className={`btn ${sel.estado_cuenta === 'activa' ? 'ghost danger' : 'primary'}`} disabled={motivo.trim().length < 5} onClick={cambiarEstado}>
                    {sel.estado_cuenta === 'activa' ? 'Desactivar cuenta' : 'Reactivar cuenta'}</button>
                </div>
                <span className="hint">Mínimo 5 caracteres. Desactivar no borra datos: se puede revertir.</span>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}

// Teléfono y consentimiento del familiar para recibir avisos de salud por WhatsApp (Ley 19.628: consentimiento expreso)
function AvisosWhatsapp({ u, escribe, onGuardado }: { u: Detalle; escribe: boolean; onGuardado: (d: Detalle) => void }) {
  const { puede } = useAuth()
  const [prueba, setPrueba] = useState<{ estado: string; motivo: string | null } | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [ed, setEd] = useState<{ telefono: string; whatsapp_habilitado: boolean; motivo: string } | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => { setEd(null); setError(null); setPrueba(null) }, [u.id_usuario])

  const enviarPrueba = async () => {
    setError(null); setPrueba(null); setEnviando(true)
    try { setPrueba(await api<{ estado: string; motivo: string | null }>('/whatsapp/prueba', { method: 'POST', body: { id_usuario: u.id_usuario } })) }
    catch (e) { setError(e) } finally { setEnviando(false) }
  }

  const guardar = async () => {
    if (!ed) return
    setError(null)
    try {
      const d = await api<Detalle>(`/usuarios/${u.id_usuario}/whatsapp`, {
        method: 'PUT', body: { telefono: ed.telefono.trim() || null, whatsapp_habilitado: ed.whatsapp_habilitado, motivo: ed.motivo },
      })
      setEd(null); onGuardado(d)
    } catch (e) { setError(e) }
  }

  return (
    <div className="wa-box">
      <h4 className="card-title" style={{ margin: '0 0 8px' }}>💬 Avisos de salud por WhatsApp</h4>
      <ErrorBox error={error} />
      {!ed ? (
        <>
          <dl className="kv">
            <dt>Teléfono</dt><dd className="mono">{u.telefono ?? '—'}</dd>
            <dt>Avisos</dt><dd>{u.whatsapp_habilitado
              ? <><span className="chip ok">✔ Autorizados</span> <span className="sub">desde {fecha(u.whatsapp_verificado)}</span></>
              : <span className="chip muted">■ No autorizados</span>}</dd>
          </dl>
          <div className="panel-actions" style={{ justifyContent: 'flex-start', marginTop: 8 }}>
            {escribe && <button className="btn ghost sm"
              onClick={() => setEd({ telefono: u.telefono ?? '', whatsapp_habilitado: u.whatsapp_habilitado, motivo: '' })}>Editar</button>}
            {puede('operacion', 'escritura') && u.whatsapp_habilitado && u.telefono &&
              <button className="btn ghost sm" onClick={enviarPrueba} disabled={enviando}>{enviando ? 'Enviando…' : 'Enviar WhatsApp de prueba'}</button>}
          </div>
          {prueba && (prueba.estado === 'fallido'
            ? <div className="alert crit" style={{ marginTop: 8 }}>No se pudo enviar: {prueba.motivo}</div>
            : <div className="alert ok" style={{ marginTop: 8 }}>Mensaje de prueba enviado. Revisa el WhatsApp del familiar; el estado se ve en «Avisos WhatsApp».</div>)}
        </>
      ) : (
        <div className="stack">
          <label className="stack">Teléfono con WhatsApp
            <input value={ed.telefono} onChange={e => setEd({ ...ed, telefono: e.target.value })} placeholder="+56 9 1234 5678" inputMode="tel" /></label>
          <label className="toggle" style={{ flexDirection: 'row' }}>
            <input type="checkbox" checked={ed.whatsapp_habilitado} onChange={e => setEd({ ...ed, whatsapp_habilitado: e.target.checked })} />
            El familiar autorizó recibir avisos de salud de su paciente por WhatsApp</label>
          <label className="stack">Cómo se obtuvo o retiró el consentimiento (queda en la auditoría)
            <input value={ed.motivo} onChange={e => setEd({ ...ed, motivo: e.target.value })} placeholder="Ej.: lo pidió por correo el 24-10" /></label>
          <div className="panel-actions">
            <button className="btn ghost sm" onClick={() => setEd(null)}>Cancelar</button>
            <button className="btn primary sm" disabled={ed.motivo.trim().length < 5} onClick={guardar}>Guardar</button>
          </div>
        </div>
      )}
    </div>
  )
}
