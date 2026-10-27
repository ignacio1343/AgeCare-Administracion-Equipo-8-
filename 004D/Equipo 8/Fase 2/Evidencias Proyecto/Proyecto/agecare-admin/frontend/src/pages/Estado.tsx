import { Fragment, useEffect, useState, type FormEvent } from 'react'
import { api, type Page } from '../api'
import { useAuth } from '../auth'
import { Card, Cargando, Chip, ErrorBox, ESTADO_GEN, fechaHora, hace, num, pct } from '../components/ui'

interface Componente {
  codigo: string; nombre: string; tecnologia: string | null; es_asincrono: boolean; estado: string; estado_desde: string
  uptime_30d: number | null; latencia_p50_ms: number | null; latencia_p95_ms: number | null; umbral_p95_ms: number; ultima_verificacion: string | null
}
interface Proceso { codigo: string; nombre: string; cadena: string; p95_segundos: number | null; exito_24h: number | null; estado: string; componentes: string[] }
interface EstadoOp { estado_general: string; resumen: string; ultima_verificacion: string | null; componentes: Componente[]; procesos: Proceso[]; incidentes_abiertos: number }
interface Incidente {
  id_incidente: number; titulo: string; componente: string | null; componente_nombre: string | null; severidad: string; estado: string
  es_mantenimiento: boolean; creado_automaticamente: boolean; descripcion: string; resolucion: string | null; responsable: string | null
  fecha_inicio: string; fecha_resolucion: string | null; transiciones_permitidas: string[]
}
interface Alertas {
  horas: number; total: number; activas: number
  por_tipo: { codigo: string; nombre: string; total: number; activas: number; atencion_min_prom: number | null }[]
  recientes: { id_alerta: number; tipo: string; paciente: string; severidad: string; estado: string; fecha_emision: string; fecha_atencion: string | null }[]
}

const BANNER: Record<string, { cls: string; ico: string; txt: string }> = {
  operativo: { cls: 'ok', ico: '✔', txt: 'Todos los sistemas operativos' },
  degradado: { cls: 'warn', ico: '▲', txt: 'Servicio degradado' },
  caido: { cls: 'crit', ico: '✖', txt: 'Hay componentes caídos' },
}
const SEV: Record<string, string> = { baja: 'neutral', media: 'warn', alta: 'serious', critica: 'crit' }

function Incidentes({ comps, escribe, recargar }: { comps: Componente[]; escribe: boolean; recargar: () => void }) {
  const [data, setData] = useState<Page<Incidente> | null>(null)
  const [nuevo, setNuevo] = useState<null | { titulo: string; descripcion: string; severidad: string; codigo_componente: string; es_mantenimiento: boolean }>(null)
  const [edit, setEdit] = useState<{ id: number; estado: string; resolucion: string; descripcion: string } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const cargar = () => api<Page<Incidente>>('/operacion/incidentes', { query: { dias: 90, page_size: 20 } }).then(setData).catch(setError)
  useEffect(() => { cargar() }, [])

  const crear = async (e: FormEvent) => {
    e.preventDefault(); setError(null)
    try {
      await api('/operacion/incidentes', { method: 'POST', body: { ...nuevo, codigo_componente: nuevo?.codigo_componente || null } })
      setNuevo(null); cargar(); recargar()
    } catch (err) { setError(err) }
  }
  const guardar = async (e: FormEvent) => {
    e.preventDefault(); if (!edit) return; setError(null)
    const body: Record<string, unknown> = {}
    if (edit.estado) body.estado = edit.estado
    if (edit.resolucion.trim()) body.resolucion = edit.resolucion.trim()
    if (edit.descripcion.trim()) body.descripcion = edit.descripcion.trim()
    try { await api(`/operacion/incidentes/${edit.id}`, { method: 'PATCH', body }); setEdit(null); cargar(); recargar() } catch (err) { setError(err) }
  }

  return (
    <Card title="Incidentes y mantenimientos" sub="CU31 · últimos 90 días · los automáticos los abre el monitor tras 3 fallas seguidas"
      actions={escribe && <button className="btn primary sm" onClick={() => setNuevo(nuevo ? null : { titulo: '', descripcion: '', severidad: 'degradado', codigo_componente: '', es_mantenimiento: false })}>
        {nuevo ? 'Cancelar' : '+ Registrar incidente'}</button>}>
      <ErrorBox error={error} />
      {nuevo && (
        <form className="form inline-form" style={{ gridTemplateColumns: '1fr 1fr' }} onSubmit={crear}>
          <label>Título<input value={nuevo.titulo} onChange={e => setNuevo({ ...nuevo, titulo: e.target.value })} required minLength={5} /></label>
          <label>Componente<select value={nuevo.codigo_componente} onChange={e => setNuevo({ ...nuevo, codigo_componente: e.target.value })}>
            <option value="">General / varios</option>{comps.map(c => <option key={c.codigo} value={c.codigo}>{c.nombre}</option>)}</select></label>
          <label className="full">Descripción<textarea value={nuevo.descripcion} onChange={e => setNuevo({ ...nuevo, descripcion: e.target.value })} required minLength={5} /></label>
          <label>Severidad<select value={nuevo.severidad} onChange={e => setNuevo({ ...nuevo, severidad: e.target.value })}>
            <option value="degradado">Degradado</option><option value="caido">Caído</option></select></label>
          <label className="toggle" style={{ flexDirection: 'row', alignSelf: 'end' }}><input type="checkbox" checked={nuevo.es_mantenimiento}
            onChange={e => setNuevo({ ...nuevo, es_mantenimiento: e.target.checked })} /> Es un mantenimiento programado</label>
          <div className="actions full"><button className="btn primary">Registrar</button></div>
        </form>
      )}
      {!data ? <Cargando /> : (
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Incidente</th><th>Severidad</th><th>Estado</th><th>Inicio</th><th>Responsable</th><th></th></tr></thead>
          <tbody>
            {data.items.map(i => (
              <Fragment key={i.id_incidente}>
                <tr>
                  <td><div className="strong">{i.titulo}</div>
                    <div className="sub">{i.componente_nombre ?? 'General'}{i.es_mantenimiento && ' · mantenimiento'}{i.creado_automaticamente && ' · abierto por el monitor'}</div>
                    {i.resolucion && <div className="sub">✔ {i.resolucion}</div>}</td>
                  <td><Chip estado={i.severidad} /></td>
                  <td><Chip estado={i.estado} /></td>
                  <td className="nowrap">{fechaHora(i.fecha_inicio)}</td>
                  <td>{i.responsable ?? <span className="muted">—</span>}</td>
                  <td className="right">{escribe && i.transiciones_permitidas.length > 0 &&
                    <button className="btn ghost sm" onClick={() => setEdit(edit?.id === i.id_incidente ? null : { id: i.id_incidente, estado: '', resolucion: '', descripcion: '' })}>Actualizar</button>}</td>
                </tr>
                {edit?.id === i.id_incidente && (
                  <tr><td colSpan={6}>
                    <form className="form" onSubmit={guardar}>
                      <label>Nuevo estado<select value={edit.estado} onChange={e => setEdit({ ...edit, estado: e.target.value })}>
                        <option value="">(sin cambio)</option>{i.transiciones_permitidas.map(t => <option key={t} value={t}>{ESTADO_GEN[t]?.label ?? t}</option>)}</select></label>
                      <label>Actualización para el equipo<input value={edit.descripcion} onChange={e => setEdit({ ...edit, descripcion: e.target.value })} placeholder="Opcional" /></label>
                      <label className="full">Resolución {['resuelto', 'completado'].includes(edit.estado) && <span className="hint">(obligatoria para cerrar)</span>}
                        <textarea value={edit.resolucion} onChange={e => setEdit({ ...edit, resolucion: e.target.value })} /></label>
                      <div className="actions full"><button type="button" className="btn ghost" onClick={() => setEdit(null)}>Cancelar</button><button className="btn primary">Guardar</button></div>
                    </form>
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>{!data.items.length && <p className="empty">Sin incidentes en el periodo.</p>}</div>
      )}
    </Card>
  )
}

// CU29 Consultar estado operativo · CU30 Monitorear alertas · CU27/28 Monitor y apertura automática · CU31 Incidentes
export default function Estado() {
  const { puede } = useAuth()
  const escribe = puede('operacion', 'escritura')
  const [est, setEst] = useState<EstadoOp | null>(null)
  const [al, setAl] = useState<Alertas | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [falla, setFalla] = useState('')
  const [aviso, setAviso] = useState('')
  const [k, setK] = useState(0)

  const cargar = () => {
    api<EstadoOp>('/operacion/estado').then(setEst).catch(setError)
    api<Alertas>('/operacion/alertas', { query: { horas: 24 } }).then(setAl).catch(setError)
  }
  useEffect(() => { cargar(); const t = setInterval(cargar, 30000); return () => clearInterval(t) }, [])

  const ciclo = async () => {
    setError(null); setAviso('')
    try {
      const nuevos = await api<Incidente[]>('/operacion/monitor/ciclo', { method: 'POST', query: { simular_falla: falla } })
      setAviso(nuevos.length ? `El monitor abrió ${nuevos.length} incidente(s) automáticamente.` : falla
        ? 'Ciclo ejecutado con falla simulada. Tras 3 fallas seguidas el componente pasa a «caído» y se abre un incidente.' : 'Ciclo de verificación ejecutado.')
      cargar(); setK(k + 1)
    } catch (e) { setError(e) }
  }

  if (!est) return <><ErrorBox error={error} /><Cargando /></>
  const b = BANNER[est.estado_general] ?? BANNER.degradado
  return (
    <>
      <div className={`banner ${b.cls}`} role="status">
        <span className="big" aria-hidden>{b.ico}</span>
        <div><b>{b.txt}</b><span className="muted">{est.resumen} · verificado {hace(est.ultima_verificacion)}</span></div>
        <span className="tb-spacer" />
        <span className="chip neutral">{est.incidentes_abiertos} incidente(s) abierto(s)</span>
      </div>
      <ErrorBox error={error} />
      {aviso && <div className="alert ok">{aviso}</div>}

      <Card title="Componentes" sub="CU27 · el monitor verifica cada minuto; p95 sobre el umbral = degradado"
        actions={escribe && (
          <div className="filters" style={{ margin: 0 }}>
            <select value={falla} onChange={e => setFalla(e.target.value)} aria-label="Simular falla">
              <option value="">Sin falla simulada</option>{est.componentes.map(c => <option key={c.codigo} value={c.codigo}>Simular falla: {c.nombre}</option>)}
            </select>
            <button className="btn ghost sm" onClick={ciclo}>Ejecutar ciclo del monitor</button>
          </div>)}>
        <div className="comp-grid">
          {est.componentes.map(c => {
            const cls = c.estado === 'operativo' ? '' : c.estado === 'caido' ? 'crit' : 'warn'
            return (
              <div key={c.codigo} className={`comp ${cls}`}>
                <div className="comp-head"><div><div className="comp-name">{c.nombre}</div><div className="small muted">{c.tecnologia}</div></div><Chip estado={c.estado} /></div>
                <div className="comp-meta">
                  <span>p50<b>{num(c.latencia_p50_ms)} ms</b></span>
                  <span>p95<b className={c.latencia_p95_ms != null && c.latencia_p95_ms > c.umbral_p95_ms ? 'over' : ''}>{num(c.latencia_p95_ms)} ms</b></span>
                  <span>Uptime 30 d<b>{pct(c.uptime_30d, 2)}</b></span>
                </div>
                <div className="small muted">Umbral p95 {num(c.umbral_p95_ms)} ms · {c.estado !== 'operativo' ? `desde ${hace(c.estado_desde)}` : `estable ${hace(c.estado_desde).replace('hace ', '')}`}</div>
              </div>
            )
          })}
        </div>
      </Card>

      <div className="grid g2">
        <Card title="Procesos críticos de cuidado" sub="Toman el peor estado de sus componentes">
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Proceso</th><th className="right">p95</th><th className="right">Éxito 24 h</th><th>Estado</th></tr></thead>
            <tbody>{est.procesos.map(p => (
              <tr key={p.codigo}><td><div className="strong">{p.nombre}</div><div className="sub">{p.cadena}</div></td>
                <td className="right nowrap">{p.p95_segundos != null ? `${num(p.p95_segundos, 1)} s` : '—'}</td>
                <td className="right">{pct(p.exito_24h)}</td><td><Chip estado={p.estado} /></td></tr>
            ))}</tbody>
          </table></div>
        </Card>
        {al && (
          <Card title="Alertas de pacientes" sub={`CU30 · últimas ${al.horas} h · ${al.total} emitidas · ${al.activas} sin atender`}>
            <div className="table-wrap"><table className="data">
              <thead><tr><th>Tipo</th><th className="right">Emitidas</th><th className="right">Activas</th><th className="right">Atención prom.</th></tr></thead>
              <tbody>{al.por_tipo.map(t => (
                <tr key={t.codigo}><td>{t.nombre}</td><td className="right">{t.total}</td>
                  <td className="right">{t.activas ? <span className="chip warn">{t.activas}</span> : 0}</td>
                  <td className="right">{t.atencion_min_prom != null ? `${num(t.atencion_min_prom, 1)} min` : '—'}</td></tr>
              ))}</tbody>
            </table></div>
            <h4 className="card-title" style={{ margin: '14px 0 6px' }}>Recientes</h4>
            <div className="table-wrap"><table className="data">
              <tbody>{al.recientes.slice(0, 6).map(a => (
                <tr key={a.id_alerta}><td><div>{a.tipo}</div><div className="sub">{a.paciente}</div></td>
                  <td><span className={`chip ${SEV[a.severidad] ?? 'neutral'}`}>{a.severidad}</span></td>
                  <td>{a.estado === 'activa' ? <span className="chip warn">◷ Sin atender</span> : <Chip estado={a.estado} />}</td><td className="nowrap">{hace(a.fecha_emision)}</td></tr>
              ))}</tbody>
            </table></div>
          </Card>
        )}
      </div>
      <Incidentes key={k} comps={est.componentes} escribe={escribe} recargar={cargar} />
    </>
  )
}
