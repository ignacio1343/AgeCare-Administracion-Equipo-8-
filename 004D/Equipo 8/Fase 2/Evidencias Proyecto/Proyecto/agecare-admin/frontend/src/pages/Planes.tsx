import { Fragment, useEffect, useState, type FormEvent } from 'react'
import { api, type Page } from '../api'
import { useAuth } from '../auth'
import { Card, Cargando, Chip, clp, ErrorBox, fecha, fechaHora, Paginacion, Tabs } from '../components/ui'

interface Plan { codigo_plan: string; nombre: string; precio: number; moneda: string; unidad_facturable: string; periodicidad: string; activo: boolean; funcionalidades: string[]; suscripciones_activas: number }
interface Func { codigo: string; nombre: string }
interface Suscripcion { id_suscripcion: number; id_cuenta: number; cuenta: string; tipo_cuenta: string; codigo_plan: string; plan: string; precio: number; estado: string
  fecha_inicio: string; inicio_periodo: string; fin_periodo: string; fecha_cancelacion: string | null; motivo_cancelacion: string | null }
interface Reembolso { id_reembolso: number; monto: number; motivo: string; estado: string; autorizador: string; fecha: string }
interface Transaccion { id_transaccion: number; id_suscripcion: number; cuenta: string; plan: string; monto: number; moneda: string; estado: string; fecha: string
  medio_pago: string | null; codigo_error: string | null; id_externo_pasarela: string | null; reembolsado: number; reembolsable: number; reembolsos: Reembolso[] }
interface Cuenta { id_cuenta: number; tipo_cuenta: string; nombre: string; email_facturacion: string; rut: string | null; estado: string; titular: string; titular_email: string
  fecha_creacion: string; suscripcion_actual: Suscripcion | null }
interface CuentaDet extends Cuenta { suscripciones: Suscripcion[]; transacciones: Transaccion[] }
interface Evento { id_evento: number; id_externo_evento: string; tipo_evento: string; id_transaccion: number | null; procesado: boolean; error_procesamiento: string | null; fecha_recepcion: string }
interface Resumen { mrr: number; suscripciones_activas: number; en_mora: number; canceladas_30d: number; ingresos_30d: number; reembolsos_30d: number; rechazos_30d: number }

// CU09 Configurar planes y funcionalidades
function TabPlanes({ escribe }: { escribe: boolean }) {
  const [planes, setPlanes] = useState<Plan[] | null>(null)
  const [funcs, setFuncs] = useState<Func[]>([])
  const [ed, setEd] = useState<{ codigo: string; nombre: string; precio: string; activo: boolean; funcionalidades: string[] } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const cargar = () => api<Plan[]>('/comercial/planes').then(setPlanes).catch(setError)
  useEffect(() => { cargar(); api<Func[]>('/comercial/funcionalidades').then(setFuncs).catch(() => {}) }, [])

  const guardar = async (e: FormEvent) => {
    e.preventDefault(); if (!ed) return; setError(null)
    try {
      await api(`/comercial/planes/${ed.codigo}`, { method: 'PUT', body: { nombre: ed.nombre, precio: Number(ed.precio), activo: ed.activo, funcionalidades: ed.funcionalidades } })
      setEd(null); cargar()
    } catch (err) { setError(err) }
  }
  const nombreF = (c: string) => funcs.find(f => f.codigo === c)?.nombre ?? c

  return (
    <Card title="Planes comerciales" sub="CU09 · el cambio de precio aplica desde el próximo periodo de cada suscripción">
      <ErrorBox error={error} />
      {!planes ? <Cargando /> : (
        <div className="plan-cards">
          {planes.map(p => (
            <div key={p.codigo_plan} className={`plan-card${p.activo ? '' : ' off'}`}>
              <div className="comp-head"><b>{p.nombre}</b>{p.activo ? <span className="chip ok">✔ Activo</span> : <span className="chip muted">■ Inactivo</span>}</div>
              <div className="precio">{clp(p.precio)} <span className="kpi-unit">/ {p.unidad_facturable} · {p.periodicidad}</span></div>
              <div className="small muted">{p.suscripciones_activas} suscripción(es) vigente(s) en la consola · {p.funcionalidades.length} funcionalidades</div>
              <div>{p.funcionalidades.slice(0, 6).map(f => <span key={f} className="chip sm neutral">{nombreF(f)}</span>)}{p.funcionalidades.length > 6 && <span className="chip sm muted">+{p.funcionalidades.length - 6}</span>}</div>
              {escribe && <button className="btn ghost sm" style={{ marginTop: 'auto' }} onClick={() => setEd({ codigo: p.codigo_plan, nombre: p.nombre, precio: String(p.precio), activo: p.activo, funcionalidades: [...p.funcionalidades] })}>Editar</button>}
            </div>
          ))}
        </div>
      )}
      {ed && (
        <form className="form" style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--line)' }} onSubmit={guardar}>
          <label>Nombre del plan<input value={ed.nombre} onChange={e => setEd({ ...ed, nombre: e.target.value })} required minLength={3} /></label>
          <label>Precio mensual (CLP) {ed.codigo === 'gratuito' && <span className="hint">el plan gratuito siempre vale $0</span>}
            <input type="number" min={0} value={ed.precio} disabled={ed.codigo === 'gratuito'} onChange={e => setEd({ ...ed, precio: e.target.value })} required /></label>
          <div className="full">
            <div className="small strong" style={{ color: 'var(--ink-soft)' }}>Funcionalidades incluidas</div>
            <div className="feat-grid">{funcs.map(f => (
              <label key={f.codigo}><input type="checkbox" checked={ed.funcionalidades.includes(f.codigo)}
                onChange={e => setEd({ ...ed, funcionalidades: e.target.checked ? [...ed.funcionalidades, f.codigo] : ed.funcionalidades.filter(x => x !== f.codigo) })} />{f.nombre}</label>
            ))}</div>
          </div>
          <label className="toggle" style={{ flexDirection: 'row' }}><input type="checkbox" checked={ed.activo} onChange={e => setEd({ ...ed, activo: e.target.checked })} /> Plan disponible para nuevas suscripciones</label>
          <div className="actions"><button type="button" className="btn ghost" onClick={() => setEd(null)}>Cancelar</button><button className="btn primary">Guardar plan</button></div>
        </form>
      )}
    </Card>
  )
}

const cuentaVacia = { email_titular: '', tipo_cuenta: 'familia', nombre: '', email_facturacion: '', rut: '', codigo_plan: '' }

// CU10 Gestionar cuentas de clientes
function TabCuentas({ escribe, planes }: { escribe: boolean; planes: Plan[] }) {
  const [data, setData] = useState<Page<Cuenta> | null>(null)
  const [f, setF] = useState({ q: '', tipo: '', page: 1 })
  const [q, setQ] = useState('')
  const [nueva, setNueva] = useState<typeof cuentaVacia | null>(null)
  const [det, setDet] = useState<CuentaDet | null>(null)
  const [error, setError] = useState<unknown>(null)
  const cargar = () => api<Page<Cuenta>>('/comercial/cuentas', { query: { ...f, page_size: 12 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [f]) // eslint-disable-line react-hooks/exhaustive-deps
  const abrir = (id: number) => api<CuentaDet>(`/comercial/cuentas/${id}`).then(setDet).catch(setError)

  const crear = async (e: FormEvent) => {
    e.preventDefault(); if (!nueva) return; setError(null)
    try {
      const c = await api<Cuenta>('/comercial/cuentas', { method: 'POST', body: { ...nueva, rut: nueva.rut || null, codigo_plan: nueva.codigo_plan || null } })
      setNueva(null); cargar(); abrir(c.id_cuenta)
    } catch (err) { setError(err) }
  }

  return (
    <div className="grid split">
      <Card title="Cuentas de clientes" sub="CU10 · familias y proveedores que pagan un plan"
        actions={escribe && <button className="btn primary sm" onClick={() => setNueva(nueva ? null : { ...cuentaVacia })}>{nueva ? 'Cancelar' : '+ Nueva cuenta'}</button>}>
        <ErrorBox error={error} />
        {nueva && (
          <form className="form inline-form" style={{ gridTemplateColumns: '1fr 1fr' }} onSubmit={crear}>
            <label>Correo del titular <span className="hint">debe ser usuario de la app</span><input type="email" value={nueva.email_titular} onChange={e => setNueva({ ...nueva, email_titular: e.target.value })} required /></label>
            <label>Tipo<select value={nueva.tipo_cuenta} onChange={e => setNueva({ ...nueva, tipo_cuenta: e.target.value })}><option value="familia">Familia</option><option value="proveedor">Proveedor</option></select></label>
            <label>Nombre de la cuenta<input value={nueva.nombre} onChange={e => setNueva({ ...nueva, nombre: e.target.value })} required minLength={3} placeholder="Familia Pérez" /></label>
            <label>Correo de facturación<input type="email" value={nueva.email_facturacion} onChange={e => setNueva({ ...nueva, email_facturacion: e.target.value })} required /></label>
            <label>RUT <span className="hint">opcional · 12.345.678-5</span><input value={nueva.rut} onChange={e => setNueva({ ...nueva, rut: e.target.value })} /></label>
            <label>Plan inicial<select value={nueva.codigo_plan} onChange={e => setNueva({ ...nueva, codigo_plan: e.target.value })}>
              <option value="">Sin suscripción</option>{planes.filter(p => p.activo).map(p => <option key={p.codigo_plan} value={p.codigo_plan}>{p.nombre} · {clp(p.precio)}</option>)}</select></label>
            <div className="actions full"><button className="btn primary">Crear cuenta</button></div>
          </form>
        )}
        <div className="filters">
          <form className="search" onSubmit={e => { e.preventDefault(); setF({ ...f, q: q.trim(), page: 1 }) }}><input placeholder="Buscar cuenta, titular o correo" value={q} onChange={e => setQ(e.target.value)} aria-label="Buscar" /></form>
          <select value={f.tipo} onChange={e => setF({ ...f, tipo: e.target.value, page: 1 })} aria-label="Tipo"><option value="">Tipo</option><option value="familia">Familia</option><option value="proveedor">Proveedor</option></select>
        </div>
        {!data ? <Cargando /> : (
          <>
            <div className="table-wrap"><table className="data clickable">
              <thead><tr><th>Cuenta</th><th>Plan</th><th>Suscripción</th><th>Renueva</th></tr></thead>
              <tbody>{data.items.map(c => (
                <tr key={c.id_cuenta} className={det?.id_cuenta === c.id_cuenta ? 'sel' : ''} tabIndex={0} onClick={() => abrir(c.id_cuenta)} onKeyDown={e => e.key === 'Enter' && abrir(c.id_cuenta)}>
                  <td><div className="strong">{c.nombre}</div><div className="sub">{c.tipo_cuenta} · {c.titular}</div></td>
                  <td>{c.suscripcion_actual?.plan ?? <span className="muted">—</span>}</td>
                  <td>{c.suscripcion_actual ? <Chip estado={c.suscripcion_actual.estado} /> : <span className="muted">—</span>}</td>
                  <td className="nowrap">{fecha(c.suscripcion_actual?.fin_periodo)}</td>
                </tr>
              ))}</tbody>
            </table></div>
            <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={p => setF({ ...f, page: p })} />
          </>
        )}
      </Card>
      <Card title={det?.nombre ?? 'Detalle de la cuenta'} sub={det ? `${det.tipo_cuenta} · creada ${fecha(det.fecha_creacion)}` : 'Selecciona una cuenta'}>
        {!det ? <p className="muted">Verás titular, historial de suscripciones y pagos.</p> : (
          <>
            <dl className="kv">
              <dt>Titular</dt><dd>{det.titular}<div className="sub">{det.titular_email}</div></dd>
              <dt>Facturación</dt><dd>{det.email_facturacion}</dd>
              <dt>RUT</dt><dd>{det.rut ?? '—'}</dd>
              <dt>Estado</dt><dd><Chip estado={det.estado} /></dd>
            </dl>
            <h4 className="card-title" style={{ margin: '14px 0 6px' }}>Suscripciones</h4>
            {det.suscripciones.map(s => <div key={s.id_suscripcion} className="small" style={{ marginBottom: 4 }}><Chip estado={s.estado} /> {s.plan} · desde {fecha(s.fecha_inicio)}{s.motivo_cancelacion && ` · «${s.motivo_cancelacion}»`}</div>)}
            {!det.suscripciones.length && <p className="muted small">Sin suscripciones.</p>}
            <h4 className="card-title" style={{ margin: '14px 0 6px' }}>Últimos pagos</h4>
            <div className="table-wrap"><table className="data"><tbody>{det.transacciones.slice(0, 8).map(t => (
              <tr key={t.id_transaccion}><td className="nowrap">{fecha(t.fecha)}</td><td className="right">{clp(t.monto)}</td><td><Chip estado={t.estado} /></td></tr>
            ))}</tbody></table></div>
          </>
        )}
      </Card>
    </div>
  )
}

// CU11 Cambiar plan · CU12 Cancelar suscripción
function TabSuscripciones({ escribe, planes }: { escribe: boolean; planes: Plan[] }) {
  const [data, setData] = useState<Page<Suscripcion> | null>(null)
  const [f, setF] = useState({ estado: '', plan: '', page: 1 })
  const [cancel, setCancel] = useState<{ id: number; motivo: string } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [aviso, setAviso] = useState('')
  const cargar = () => api<Page<Suscripcion>>('/comercial/suscripciones', { query: { ...f, page_size: 15 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [f]) // eslint-disable-line react-hooks/exhaustive-deps

  const cambiar = async (s: Suscripcion, codigo_plan: string) => {
    setError(null); setAviso('')
    try { await api(`/comercial/suscripciones/${s.id_suscripcion}/plan`, { method: 'PATCH', body: { codigo_plan } }); setAviso(`${s.cuenta}: plan cambiado.`); cargar() } catch (e) { setError(e) }
  }
  const cancelar = async (e: FormEvent) => {
    e.preventDefault(); if (!cancel) return; setError(null)
    try { await api(`/comercial/suscripciones/${cancel.id}/cancelar`, { method: 'POST', body: { motivo: cancel.motivo } }); setCancel(null); setAviso('Suscripción cancelada en la pasarela (simulada).'); cargar() } catch (err) { setError(err) }
  }

  return (
    <Card title="Suscripciones" sub="CU11 cambiar de plan · CU12 cancelar (se informa a la pasarela de pagos)">
      <div className="filters">
        <select value={f.estado} onChange={e => setF({ ...f, estado: e.target.value, page: 1 })} aria-label="Estado"><option value="">Estado</option>
          {['activa', 'en_mora', 'cancelada', 'vencida'].map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}</select>
        <select value={f.plan} onChange={e => setF({ ...f, plan: e.target.value, page: 1 })} aria-label="Plan"><option value="">Plan</option>
          {planes.map(p => <option key={p.codigo_plan} value={p.codigo_plan}>{p.nombre}</option>)}</select>
      </div>
      <ErrorBox error={error} />
      {aviso && <div className="alert ok">{aviso}</div>}
      {!data ? <Cargando /> : (
        <>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Cuenta</th><th>Plan</th><th>Estado</th><th>Periodo actual</th><th></th></tr></thead>
            <tbody>{data.items.map(s => {
              const vigente = ['activa', 'en_mora'].includes(s.estado)
              return (
                <Fragment key={s.id_suscripcion}>
                  <tr>
                    <td><div className="strong">{s.cuenta}</div><div className="sub">{s.tipo_cuenta}</div></td>
                    <td>{escribe && vigente ? (
                      <select value={s.codigo_plan} onChange={e => cambiar(s, e.target.value)} aria-label={`Plan de ${s.cuenta}`}>
                        {planes.filter(p => p.activo || p.codigo_plan === s.codigo_plan).map(p => <option key={p.codigo_plan} value={p.codigo_plan}>{p.nombre} · {clp(p.precio)}</option>)}</select>
                    ) : <>{s.plan}<div className="sub">{clp(s.precio)}</div></>}</td>
                    <td><Chip estado={s.estado} />{s.motivo_cancelacion && <div className="sub">{s.motivo_cancelacion}</div>}</td>
                    <td className="nowrap">{fecha(s.inicio_periodo)} → {fecha(s.fin_periodo)}</td>
                    <td className="right">{escribe && vigente && <button className="btn ghost sm danger" onClick={() => setCancel(cancel?.id === s.id_suscripcion ? null : { id: s.id_suscripcion, motivo: '' })}>Cancelar</button>}</td>
                  </tr>
                  {cancel?.id === s.id_suscripcion && (
                    <tr><td colSpan={5}><form className="mod-form" onSubmit={cancelar}>
                      <input placeholder="Motivo de la cancelación (mín. 5 caracteres)" value={cancel.motivo} onChange={e => setCancel({ ...cancel, motivo: e.target.value })} required minLength={5} aria-label="Motivo" />
                      <button className="btn primary sm" disabled={cancel.motivo.trim().length < 5}>Confirmar cancelación</button>
                    </form></td></tr>
                  )}
                </Fragment>
              )
            })}</tbody>
          </table></div>
          <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={p => setF({ ...f, page: p })} />
        </>
      )}
    </Card>
  )
}

// CU13 Consultar transacciones · CU15 Emitir reembolso
function TabTransacciones({ escribe }: { escribe: boolean }) {
  const [data, setData] = useState<Page<Transaccion> | null>(null)
  const [f, setF] = useState({ estado: '', dias: 90, page: 1 })
  const [reem, setReem] = useState<{ id: number; monto: string; motivo: string } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const cargar = () => api<Page<Transaccion>>('/comercial/transacciones', { query: { ...f, page_size: 15 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [f]) // eslint-disable-line react-hooks/exhaustive-deps

  const reembolsar = async (e: FormEvent) => {
    e.preventDefault(); if (!reem) return; setError(null)
    try { await api(`/comercial/transacciones/${reem.id}/reembolsos`, { method: 'POST', body: { monto: Number(reem.monto), motivo: reem.motivo } }); setReem(null); cargar() } catch (err) { setError(err) }
  }

  return (
    <Card title="Transacciones" sub="CU13 · pagos informados por la pasarela · CU15 reembolso total o parcial">
      <div className="filters">
        <select value={f.estado} onChange={e => setF({ ...f, estado: e.target.value, page: 1 })} aria-label="Estado"><option value="">Estado</option>
          <option value="aprobada">Aprobadas</option><option value="rechazada">Rechazadas</option><option value="pendiente">Pendientes</option></select>
        <select value={f.dias} onChange={e => setF({ ...f, dias: Number(e.target.value), page: 1 })} aria-label="Periodo">
          <option value={30}>Últimos 30 días</option><option value={90}>Últimos 90 días</option><option value={365}>Último año</option></select>
      </div>
      <ErrorBox error={error} />
      {!data ? <Cargando /> : (
        <>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Fecha</th><th>Cuenta</th><th className="right">Monto</th><th>Estado</th><th>Medio</th><th></th></tr></thead>
            <tbody>{data.items.map(t => (
              <Fragment key={t.id_transaccion}>
                <tr>
                  <td className="nowrap">{fechaHora(t.fecha)}<div className="sub mono">{t.id_externo_pasarela}</div></td>
                  <td><div>{t.cuenta}</div><div className="sub">{t.plan}</div></td>
                  <td className="right"><b>{clp(t.monto)}</b>{t.reembolsado > 0 && <div className="sub">− {clp(t.reembolsado)} reemb.</div>}</td>
                  <td><Chip estado={t.estado} />{t.codigo_error && <div className="sub">{t.codigo_error.replace(/_/g, ' ')}</div>}</td>
                  <td>{t.medio_pago ?? '—'}</td>
                  <td className="right">{escribe && t.reembolsable > 0 && <button className="btn ghost sm" onClick={() => setReem(reem?.id === t.id_transaccion ? null : { id: t.id_transaccion, monto: String(t.reembolsable), motivo: '' })}>Reembolsar</button>}</td>
                </tr>
                {reem?.id === t.id_transaccion && (
                  <tr><td colSpan={6}><form className="mod-form" onSubmit={reembolsar}>
                    <label className="small">Monto (máx. {clp(t.reembolsable)})</label>
                    <input type="number" min={1} max={t.reembolsable} value={reem.monto} onChange={e => setReem({ ...reem, monto: e.target.value })} style={{ flex: 'none', width: 120 }} aria-label="Monto" />
                    <input placeholder="Motivo (mín. 5 caracteres)" value={reem.motivo} onChange={e => setReem({ ...reem, motivo: e.target.value })} required minLength={5} aria-label="Motivo" />
                    <button className="btn primary sm" disabled={reem.motivo.trim().length < 5}>Emitir reembolso</button>
                  </form></td></tr>
                )}
                {t.reembolsos.map(r => (
                  <tr key={`r${r.id_reembolso}`}><td colSpan={6} className="small muted">↺ Reembolso {clp(r.monto)} · {r.motivo} · {r.autorizador} · {fechaHora(r.fecha)}</td></tr>
                ))}
              </Fragment>
            ))}</tbody>
          </table></div>
          <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={p => setF({ ...f, page: p })} />
        </>
      )}
    </Card>
  )
}

// CU14 Registrar evento de pago (lo envía la pasarela por webhook firmado)
function TabEventos() {
  const [data, setData] = useState<Page<Evento> | null>(null)
  const [page, setPage] = useState(1)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => { api<Page<Evento>>('/comercial/eventos-pago', { query: { page, page_size: 20 } }).then(setData).catch(setError) }, [page])
  return (
    <Card title="Eventos de pago recibidos" sub="CU14 · la pasarela llama a POST /api/v1/pagos/webhook con firma HMAC; los duplicados se ignoran">
      <ErrorBox error={error} />
      {!data ? <Cargando /> : (
        <>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Recibido</th><th>Evento</th><th>Tipo</th><th>Transacción</th><th>Resultado</th></tr></thead>
            <tbody>{data.items.map(e => (
              <tr key={e.id_evento}><td className="nowrap">{fechaHora(e.fecha_recepcion)}</td><td className="mono">{e.id_externo_evento}</td><td>{e.tipo_evento}</td>
                <td>{e.id_transaccion ?? '—'}</td>
                <td>{e.procesado ? <span className="chip ok">✔ Procesado</span> : <span className="chip crit">✖ {e.error_procesamiento ?? 'Error'}</span>}</td></tr>
            ))}</tbody>
          </table>{!data.items.length && <p className="empty">Aún no llegan eventos. El README explica cómo simular uno.</p>}</div>
          <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
        </>
      )}
    </Card>
  )
}

type Tab = 'planes' | 'cuentas' | 'suscripciones' | 'transacciones' | 'eventos'
export default function Planes() {
  const { puede } = useAuth()
  const escribe = puede('comercial', 'escritura')
  const [tab, setTab] = useState<Tab>('planes')
  const [res, setRes] = useState<Resumen | null>(null)
  const [planes, setPlanes] = useState<Plan[]>([])
  useEffect(() => {
    api<Resumen>('/comercial/resumen').then(setRes).catch(() => {})
    api<Plan[]>('/comercial/planes').then(setPlanes).catch(() => {})
  }, [tab])
  return (
    <>
      {res && (
        <div className="kpis k4">
          <div className="kpi"><div className="kpi-label">MRR (cuentas en consola)</div><div className="kpi-value">{clp(res.mrr)}</div><div className="kpi-delta">{res.suscripciones_activas} suscripciones activas</div></div>
          <div className="kpi"><div className="kpi-label">En mora</div><div className="kpi-value">{res.en_mora}</div><div className={`kpi-delta ${res.en_mora ? 'down' : 'up'}`}>{res.rechazos_30d} pago(s) rechazado(s) · 30 d</div></div>
          <div className="kpi"><div className="kpi-label">Ingresos · 30 d</div><div className="kpi-value">{clp(res.ingresos_30d)}</div><div className="kpi-delta">{clp(res.reembolsos_30d)} reembolsado</div></div>
          <div className="kpi"><div className="kpi-label">Cancelaciones · 30 d</div><div className="kpi-value">{res.canceladas_30d}</div></div>
        </div>
      )}
      <Tabs value={tab} onChange={setTab} items={[['planes', 'Planes'], ['cuentas', 'Cuentas'], ['suscripciones', 'Suscripciones'], ['transacciones', 'Transacciones'], ['eventos', 'Eventos de pago']]} />
      {tab === 'planes' && <TabPlanes escribe={escribe} />}
      {tab === 'cuentas' && <TabCuentas escribe={escribe} planes={planes} />}
      {tab === 'suscripciones' && <TabSuscripciones escribe={escribe} planes={planes} />}
      {tab === 'transacciones' && <TabTransacciones escribe={escribe} />}
      {tab === 'eventos' && <TabEventos />}
    </>
  )
}
