import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, type Indicadores, type Page, type Ref, type Ticket } from '../api'
import { useAuth } from '../auth'
import { Card, Cargando, ErrorBox, EstadoChip, ESTADOS, hace, Paginacion, PERFILES, PrioridadChip, PRIORIDADES } from '../components/ui'

const PAGE_SIZE = 15

// CU25 · Indicadores de soporte
function Kpis({ ind }: { ind: Indicadores }) {
  const objetivo = 4 // horas: objetivo de primera respuesta del wireframe
  const pr = ind.primera_respuesta_horas_prom
  return (
    <div className="kpis">
      <div className="kpi"><div className="kpi-label">Abiertos</div><div className="kpi-value">{ind.abiertos}</div>
        <div className="kpi-delta">{ind.sin_asignar} sin asignar</div></div>
      <div className="kpi"><div className="kpi-label">En curso</div><div className="kpi-value">{ind.en_curso}</div>
        <div className="kpi-delta">{ind.esperando_usuario} esperando al usuario</div></div>
      <div className="kpi"><div className="kpi-label">Resueltos · 30 d</div><div className="kpi-value">{ind.resueltos_30d}</div>
        <div className="kpi-delta">{ind.resolucion_horas_prom != null ? `${ind.resolucion_horas_prom.toLocaleString('es-CL')} h prom. resolución` : '—'}</div></div>
      <div className="kpi"><div className="kpi-label">Primera respuesta</div>
        <div className="kpi-value">{pr != null ? `${pr.toLocaleString('es-CL')} h` : '—'}</div>
        <div className={`kpi-delta ${pr != null && pr <= objetivo ? 'up' : 'down'}`}>Objetivo: &lt; {objetivo} h</div>
        <div className="kpi-note">Promedio 30 días · OE1</div></div>
      <div className="kpi"><div className="kpi-label">Satisfacción (CSAT)</div>
        <div className="kpi-value">{ind.csat_promedio?.toLocaleString('es-CL') ?? '—'}<span className="kpi-unit"> / 5</span></div>
        <div className="kpi-delta">n = {ind.csat_respuestas} encuestas</div></div>
    </div>
  )
}

function PorCategoria({ ind }: { ind: Indicadores }) {
  const max = Math.max(1, ...ind.por_categoria_30d.map(c => c.total))
  const total = ind.por_categoria_30d.reduce((a, c) => a + c.total, 0)
  return (
    <Card title="Tickets por categoría" sub={`Últimos 30 días · ${total} tickets`}>
      <div className="bars">
        {ind.por_categoria_30d.map(c => (
          <div className="bar-row" key={c.codigo}>
            <span className="bar-label">{c.nombre}</span>
            <span className="bar-track"><span className="bar" style={{ width: `${(c.total / max) * 100}%` }} /></span>
            <span className="bar-val">{c.total}</span>
          </div>
        ))}
        {!total && <p className="muted">Sin tickets en el periodo.</p>}
      </div>
    </Card>
  )
}

export default function Soporte() {
  const { puede } = useAuth()
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const [ind, setInd] = useState<Indicadores | null>(null)
  const [data, setData] = useState<Page<Ticket> | null>(null)
  const [cats, setCats] = useState<Ref[]>([])
  const [agentes, setAgentes] = useState<Ref[]>([])
  const [error, setError] = useState<unknown>(null)
  const [q, setQ] = useState(sp.get('q') ?? '')

  const f = {
    vista: sp.get('vista') ?? 'activos', estado: sp.get('estado') ?? '', prioridad: sp.get('prioridad') ?? '',
    categoria: sp.get('categoria') ?? '', asignado: sp.get('asignado') ?? '', orden: sp.get('orden') ?? '-fecha_creacion',
    q: sp.get('q') ?? '', page: Number(sp.get('page') ?? 1),
  }
  const set = (k: string, v: string) => {
    const n = new URLSearchParams(sp)
    if (v) n.set(k, v); else n.delete(k)
    if (k !== 'page') n.delete('page')
    setSp(n, { replace: true })
  }

  useEffect(() => {
    api<Indicadores>('/soporte/indicadores').then(setInd).catch(setError)
    api<Ref[]>('/soporte/categorias').then(setCats).catch(() => {})
    api<Ref[]>('/soporte/agentes').then(setAgentes).catch(() => {})
  }, [])

  useEffect(() => {
    setError(null)
    api<Page<Ticket>>('/soporte/tickets', {
      query: {
        activos: f.vista === 'activos' && !f.estado, estado: f.estado, prioridad: f.prioridad, categoria: f.categoria,
        asignado: f.vista === 'mios' ? 'yo' : f.asignado, q: f.q, orden: f.orden, page: f.page, page_size: PAGE_SIZE,
      },
    }).then(setData).catch(setError)
  }, [sp.toString()]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {ind ? <Kpis ind={ind} /> : <Cargando />}
      <div className="grid soporte-grid">
        <Card
          title="Cola de tickets"
          sub="CU35 · ordena, filtra y abre un ticket para atenderlo"
          actions={puede('soporte', 'escritura') && <Link to="/soporte/nuevo" className="btn primary sm">+ Registrar ticket</Link>}>
          <div className="filters">
            <div className="seg" role="tablist" aria-label="Vista">
              {[['activos', 'Activos'], ['mios', 'Asignados a mí'], ['todos', 'Todos']].map(([k, l]) => (
                <button key={k} className={f.vista === k ? 'on' : ''} onClick={() => set('vista', k === 'activos' ? '' : k)}>{l}</button>
              ))}
            </div>
            <form className="search" onSubmit={e => { e.preventDefault(); set('q', q.trim()) }}>
              <input placeholder="Buscar #número, asunto, nombre o correo" value={q} onChange={e => setQ(e.target.value)} aria-label="Buscar" />
            </form>
            <select value={f.estado} onChange={e => set('estado', e.target.value)} aria-label="Estado">
              <option value="">Estado</option>{Object.entries(ESTADOS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
            <select value={f.prioridad} onChange={e => set('prioridad', e.target.value)} aria-label="Prioridad">
              <option value="">Prioridad</option>{Object.entries(PRIORIDADES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
            <select value={f.categoria} onChange={e => set('categoria', e.target.value)} aria-label="Categoría">
              <option value="">Categoría</option>{cats.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
            {f.vista !== 'mios' && (
              <select value={f.asignado} onChange={e => set('asignado', e.target.value)} aria-label="Asignado">
                <option value="">Asignado</option><option value="sin_asignar">Sin asignar</option>
                {agentes.map(a => <option key={a.id} value={a.id}>{a.nombre}</option>)}
              </select>
            )}
            <select value={f.orden} onChange={e => set('orden', e.target.value)} aria-label="Orden">
              <option value="-fecha_creacion">Más nuevos</option><option value="fecha_creacion">Más antiguos</option>
              <option value="-prioridad">Mayor prioridad</option><option value="-fecha_actualizacion">Actividad reciente</option>
            </select>
          </div>
          <ErrorBox error={error} />
          {!data ? <Cargando /> : (
            <>
              <div className="table-wrap">
                <table className="data clickable">
                  <thead><tr><th>N.º</th><th>Asunto</th><th>Solicitante</th><th>Prioridad</th><th>Estado</th><th>Asignado</th><th>Creado</th></tr></thead>
                  <tbody>
                    {data.items.map(t => (
                      <tr key={t.id_ticket} onClick={() => nav(`/soporte/${t.id_ticket}`)} tabIndex={0}
                        onKeyDown={e => e.key === 'Enter' && nav(`/soporte/${t.id_ticket}`)}>
                        <td className="mono">#{t.numero}</td>
                        <td><div className="strong">{t.asunto}</div><div className="sub">{t.categoria.nombre}</div></td>
                        <td><div>{t.solicitante.nombre}</div><div className="sub">{t.solicitante.perfiles.map(p => PERFILES[p] ?? p).join(', ') || 'Sin cuenta enlazada'}</div></td>
                        <td><PrioridadChip prioridad={t.prioridad} /></td>
                        <td><EstadoChip estado={t.estado} /></td>
                        <td>{t.asignado?.nombre ?? <span className="muted">—</span>}</td>
                        <td className="nowrap" title={new Date(t.fecha_creacion).toLocaleString('es-CL')}>{hace(t.fecha_creacion)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!data.items.length && <p className="empty">No hay tickets con esos filtros.</p>}
              </div>
              <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={p => set('page', String(p))} />
            </>
          )}
        </Card>
        {ind && <PorCategoria ind={ind} />}
      </div>
    </>
  )
}
