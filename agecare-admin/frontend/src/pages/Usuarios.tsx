import { useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { useAuth } from '../auth'
import { Card, Cargando, Chip, ErrorBox, fecha, fechaHora, hace, Paginacion, PERFILES } from '../components/ui'

interface Usuario {
  id_usuario: number; nombre: string; rut: string | null; email: string; estado_cuenta: string; perfiles: string[]; pacientes: string[]
  fecha_registro: string; ultimo_acceso: string | null
}
interface Membresia { id_paciente: number; paciente: string; rol_en_circulo: string; estado: string; fecha_invitacion: string; fecha_aceptacion: string | null }
interface Detalle extends Usuario {
  membresias: Membresia[]; tickets_total: number; tickets_abiertos: number
  telefono: string | null; whatsapp_habilitado: boolean; whatsapp_verificado: string | null
  origen: string; acceso_portal: boolean; debe_cambiar_password: boolean; vistas_portal: string[]; id_paciente_propio: number | null
  fecha_aceptacion_terminos: string | null
}
interface ResidenteRef { id_paciente: number; nombre: string; rut: string | null; plan: string | null; representantes: string[]; cuidadores: string[] }
const ORIGEN: Record<string, string> = { plataforma: 'App AgeCare', portal: 'Se registró en el portal', consola: 'Creado por soporte' }

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
  const [creando, setCreando] = useState(false)
  const [temporal, setTemporal] = useState<{ clave: string; para: string } | null>(null)

  const cargar = () => api<Page<Usuario>>('/usuarios', { query: { ...f, page_size: 15 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [f]) // eslint-disable-line react-hooks/exhaustive-deps
  const abrir = (id: number, limpiar = true) => {
    if (limpiar) { setAviso(''); setTemporal(null) }
    setCreando(false)
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
      <Card title="Usuarios de la app" sub="CU32 · busca por nombre, correo, RUT o nombre del paciente"
        actions={escribe && <button className="btn primary sm" onClick={() => { setCreando(true); setSel(null); setTemporal(null); setAviso('') }}>＋ Nuevo usuario</button>}>
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
                    <td><div className="strong">{u.nombre}</div><div className="sub">{u.email}{u.rut ? ` · ${u.rut}` : ''}</div></td>
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

      <Card title={creando ? 'Nuevo usuario' : sel ? sel.nombre : 'Ficha del usuario'}
        sub={creando ? 'CU54 · representante, cuidador o residente con acceso al portal' : sel ? sel.email : 'Selecciona una fila para ver el detalle'}>
        <ErrorBox error={error} />
        {aviso && <div className="alert ok">{aviso}</div>}
        {temporal && <ClaveTemporal {...temporal} />}
        {creando ? <NuevoUsuario onCancelar={() => setCreando(false)} onCreado={(id, clave, nombre) => {
          setTemporal({ clave, para: nombre }); setAviso(`${nombre} quedó creado.`); abrir(id, false); cargar()
        }} /> : !sel ? <p className="muted">Aquí verás perfiles, círculos de cuidado y acciones de soporte.</p> : (
          <>
            <dl className="kv">
              <dt>Estado</dt><dd><Chip estado={sel.estado_cuenta} /></dd>
              <dt>Perfiles</dt><dd>{sel.perfiles.map(p => PERFILES[p] ?? p).join(', ')}</dd>
              {sel.rut && <><dt>RUT</dt><dd className="mono">{sel.rut}</dd></>}
              <dt>Origen</dt><dd>{ORIGEN[sel.origen] ?? sel.origen}</dd>
              <dt>Portal web</dt><dd>{sel.vistas_portal.length === 0 ? <span className="muted">Sin vista en el portal</span>
                : !sel.acceso_portal ? <span className="chip muted">Sin contraseña</span>
                : sel.debe_cambiar_password ? <span className="chip warn">Clave temporal pendiente de cambio</span>
                : <span className="chip ok">✔ Activo</span>}</dd>
              {sel.fecha_aceptacion_terminos && <><dt>Términos</dt><dd>Aceptados el {fecha(sel.fecha_aceptacion_terminos)}</dd></>}
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
            {escribe && (sel.vistas_portal.includes('representante') || sel.vistas_portal.includes('cuidador')) && (
              <AsignarResidente u={sel} onCambio={(d, txt) => { setSel(d); setAviso(txt) }} onError={setError} />
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
                {sel.vistas_portal.length > 0 && (
                  <div className="wa-box">
                    <h4 className="card-title" style={{ margin: '0 0 6px' }}>🔑 Contraseña del portal</h4>
                    <p className="hint" style={{ marginBottom: 8 }}>Responde a «¿Olvidaste tu contraseña?»: genera una clave temporal para entregarla por teléfono tras validar la identidad. El portal pedirá cambiarla.</p>
                    <button className="btn ghost sm" disabled={motivo.trim().length < 5} onClick={async () => {
                      setError(null)
                      try {
                        const r = await api<{ password_temporal: string }>(`/usuarios/${sel.id_usuario}/restablecer-password`, { method: 'POST', body: { motivo } })
                        setTemporal({ clave: r.password_temporal, para: sel.nombre }); setAviso(''); abrir(sel.id_usuario, false)
                      } catch (e) { setError(e) }
                    }}>Restablecer contraseña</button>
                    <span className="hint"> Usa el campo «Motivo» de arriba (p. ej. «Ticket #1047, identidad validada por teléfono»).</span>
                  </div>
                )}
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


function ClaveTemporal({ clave, para }: { clave: string; para: string }) {
  const [copiada, setCopiada] = useState(false)
  return (
    <div className="alert info">
      <b>Clave temporal de {para}</b> — se muestra solo esta vez. Entrégala por teléfono; al entrar al portal (/portal) deberá cambiarla.
      <div className="copy"><code>{clave}</code>
        <button className="btn ghost sm" onClick={() => { navigator.clipboard?.writeText(clave); setCopiada(true) }}>{copiada ? 'Copiada' : 'Copiar'}</button></div>
    </div>
  )
}

// CU55 · Residentes a cargo de un representante o de un cuidador
function AsignarResidente({ u, onCambio, onError }: { u: Detalle; onCambio: (d: Detalle, txt: string) => void; onError: (e: unknown) => void }) {
  const [q, setQ] = useState('')
  const [ops, setOps] = useState<ResidenteRef[]>([])
  useEffect(() => { api<ResidenteRef[]>('/usuarios/residentes/opciones', { query: { q } }).then(setOps).catch(() => {}) }, [q])
  const activos = new Set(u.membresias.filter(m => m.estado === 'activo').map(m => m.id_paciente))
  const asignar = async (id: number) => {
    try { onCambio(await api<Detalle>(`/usuarios/${u.id_usuario}/residentes`, { method: 'POST', body: { id_paciente: id } }), 'Residente asignado.') }
    catch (e) { onError(e) }
  }
  const quitar = async (id: number) => {
    try { onCambio(await api<Detalle>(`/usuarios/${u.id_usuario}/residentes/${id}`, { method: 'DELETE' }), 'Residente quitado.') }
    catch (e) { onError(e) }
  }
  const rol = u.vistas_portal.includes('representante') ? 'representante' : 'cuidador'
  return (
    <div className="wa-box">
      <h4 className="card-title" style={{ margin: '0 0 6px' }}>👵 Residentes a cargo ({rol})</h4>
      {u.membresias.filter(m => m.estado === 'activo').map(m => (
        <div key={m.id_paciente} className="panel-actions" style={{ justifyContent: 'space-between', marginTop: 4, alignItems: 'center' }}>
          <span className="strong">{m.paciente}</span><button className="btn ghost sm danger" onClick={() => quitar(m.id_paciente)}>Quitar</button>
        </div>
      ))}
      <input className="inline" style={{ width: '100%', marginTop: 10 }} placeholder="Buscar residente por nombre o RUT" value={q} onChange={e => setQ(e.target.value)} />
      <div style={{ maxHeight: 180, overflow: 'auto', marginTop: 6 }}>
        {ops.filter(o => !activos.has(o.id_paciente)).slice(0, 8).map(o => (
          <div key={o.id_paciente} className="panel-actions" style={{ justifyContent: 'space-between', marginTop: 4, alignItems: 'center' }}>
            <span>{o.nombre} <span className="sub">{o.rut ?? ''} {o.plan ? `· ${o.plan}` : '· sin plan'}</span></span>
            <button className="btn ghost sm" onClick={() => asignar(o.id_paciente)}>Asignar</button>
          </div>
        ))}
      </div>
    </div>
  )
}

// CU54 · Crear representante, cuidador o residente (con clave temporal)
function NuevoUsuario({ onCancelar, onCreado }: { onCancelar: () => void; onCreado: (id: number, clave: string, nombre: string) => void }) {
  const [f, setF] = useState({ perfil: 'representante', rut: '', nombres: '', primer_apellido: '', segundo_apellido: '', email: '', pais: 'CL',
                              telefono: '', whatsapp_habilitado: false, fecha_nacimiento: '', id_representante: '', codigo_plan: 'gratuito' })
  const [reps, setReps] = useState<Usuario[]>([])
  const [qRep, setQRep] = useState('')
  const [planes, setPlanes] = useState<{ codigo_plan: string; nombre: string }[]>([])
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    if (f.perfil === 'residente') api<Page<Usuario>>('/usuarios', { query: { perfil: 'familiar', q: qRep, page_size: 20 } }).then(p => setReps(p.items)).catch(() => {})
  }, [f.perfil, qRep])
  useEffect(() => { api<{ codigo_plan: string; nombre: string }[]>('/comercial/planes').then(setPlanes).catch(() =>
    setPlanes([{ codigo_plan: 'gratuito', nombre: 'Gratuito' }, { codigo_plan: 'dorado', nombre: 'Dorado' }, { codigo_plan: 'platino', nombre: 'Platino' }, { codigo_plan: 'proveedor', nombre: 'Proveedor' }])) }, [])
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value })
  const crear = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const res = f.perfil === 'residente'
    try {
      const r = await api<{ usuario: Detalle; password_temporal: string }>('/usuarios', { method: 'POST', body: {
        perfil: f.perfil, rut: f.rut, nombres: f.nombres, primer_apellido: f.primer_apellido, segundo_apellido: f.segundo_apellido || null,
        email: f.email, pais: f.pais, telefono: f.telefono || null, whatsapp_habilitado: f.whatsapp_habilitado,
        fecha_nacimiento: res ? f.fecha_nacimiento || null : null, id_representante: res && f.id_representante ? Number(f.id_representante) : null,
        codigo_plan: f.codigo_plan } })
      onCreado(r.usuario.id_usuario, r.password_temporal, r.usuario.nombre)
    } catch (x) { setError(x) }
  }
  const res = f.perfil === 'residente'
  return (
    <form className="form" onSubmit={crear}>
      <ErrorBox error={error} />
      <label className="full">Perfil
        <select value={f.perfil} onChange={set('perfil')}>
          <option value="representante">Representante (familiar que contrata y paga)</option>
          <option value="cuidador">Cuidador/a (registra la ficha vital)</option>
          <option value="residente">Residente (adulto mayor)</option>
        </select></label>
      <label>RUT<input value={f.rut} onChange={set('rut')} placeholder="12.345.678-5" required /></label>
      <label>{res ? 'Primer nombre' : 'Nombres'}<input value={f.nombres} onChange={set('nombres')} required /></label>
      <label>Primer apellido<input value={f.primer_apellido} onChange={set('primer_apellido')} required /></label>
      <label>Segundo apellido<input value={f.segundo_apellido} onChange={set('segundo_apellido')} /></label>
      <label className="full">Correo<input type="email" value={f.email} onChange={set('email')} required /></label>
      {res ? <>
        <label>Fecha de nacimiento<input type="date" value={f.fecha_nacimiento} onChange={set('fecha_nacimiento')} required /></label>
        <label>Plan (asignado por soporte, sin cobro)
          <select value={f.codigo_plan} onChange={set('codigo_plan')}>{planes.map(p => <option key={p.codigo_plan} value={p.codigo_plan}>{p.nombre}</option>)}</select></label>
        <label className="full">Representante
          <input placeholder="Buscar representante por nombre, correo o RUT" value={qRep} onChange={e => setQRep(e.target.value)} />
          <select value={f.id_representante} onChange={set('id_representante')} required>
            <option value="">— Elige —</option>{reps.map(r => <option key={r.id_usuario} value={r.id_usuario}>{r.nombre} · {r.email}</option>)}
          </select>
          <span className="hint">Si no aparece, créalo primero como representante.</span></label>
      </> : <>
        <label>País
          <select value={f.pais} onChange={set('pais')}>
            {[['CL', 'Chile (+56)'], ['AR', 'Argentina (+54)'], ['PE', 'Perú (+51)'], ['BO', 'Bolivia (+591)'], ['CO', 'Colombia (+57)'], ['VE', 'Venezuela (+58)'], ['ES', 'España (+34)']]
              .map(([c, t]) => <option key={c} value={c}>{t}</option>)}
          </select></label>
        <label>Teléfono celular<input value={f.telefono} onChange={set('telefono')} placeholder="9 1234 5678" inputMode="tel" /></label>
        {f.perfil === 'representante' && <label className="full toggle" style={{ flexDirection: 'row' }}>
          <input type="checkbox" checked={f.whatsapp_habilitado} onChange={set('whatsapp_habilitado')} />
          Autorizó recibir avisos de riesgo por WhatsApp (consentimiento expreso)</label>}
      </>}
      <div className="actions full">
        <button type="button" className="btn ghost" onClick={onCancelar}>Cancelar</button>
        <button className="btn primary">Crear y generar clave temporal</button>
      </div>
      <p className="hint full">{res ? 'Se crea la cuenta del residente, su ficha y la suscripción en la cuenta del representante.'
        : 'Después de crearlo podrás asignarle residentes desde su ficha.'}</p>
    </form>
  )
}
