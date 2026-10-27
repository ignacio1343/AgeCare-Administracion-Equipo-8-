import { useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { useAuth } from '../auth'
import { Card, Cargando, Chip, ErrorBox, fechaHora, hace, Paginacion } from '../components/ui'

interface Elemento {
  id_elemento: number; tipo_elemento: string; contenido_reportado: string; motivo_reporte: string | null; es_reporte_seguridad: boolean
  estado: string; autor: string; autor_rechazos_90d: number; reportante: string | null; motivo_rechazo: string | null
  nota_decision: string | null; decisor: string | null; fecha_creacion: string; fecha_decision: string | null
}
interface Resumen { pendientes: number; pendientes_seguridad: number; decididos_hoy: number }

const TIPOS: Record<string, string> = { resena: 'Reseña', foto: 'Foto', mensaje: 'Mensaje', perfil: 'Perfil' }
const MOTIVOS: Record<string, string> = { ofensivo: 'Ofensivo o abusivo', spam: 'Spam o publicidad', privacidad: 'Expone datos privados', fuera_de_tema: 'Fuera de tema', otro: 'Otro (explica en la nota)' }

// CU16 Moderar contenido reportado
export default function Moderacion() {
  const { puede } = useAuth()
  const escribe = puede('moderacion', 'escritura')
  const [res, setRes] = useState<Resumen | null>(null)
  const [data, setData] = useState<Page<Elemento> | null>(null)
  const [f, setF] = useState({ estado: 'pendiente', tipo: '', page: 1 })
  const [dec, setDec] = useState<Record<number, { motivo: string; nota: string }>>({})
  const [error, setError] = useState<unknown>(null)

  const cargar = () => {
    api<Resumen>('/moderacion/resumen').then(setRes).catch(setError)
    api<Page<Elemento>>('/moderacion/cola', { query: { ...f, page_size: 10 } }).then(setData).catch(setError)
  }
  useEffect(() => { cargar() }, [f]) // eslint-disable-line react-hooks/exhaustive-deps

  const decidir = async (el: Elemento, decision: 'aprobado' | 'rechazado') => {
    const d = dec[el.id_elemento] ?? { motivo: '', nota: '' }
    setError(null)
    try {
      await api(`/moderacion/${el.id_elemento}/decision`, {
        method: 'POST', body: { decision, motivo_rechazo: decision === 'rechazado' ? d.motivo || null : null, nota_decision: d.nota.trim() || null },
      })
      cargar()
    } catch (e) { setError(e) }
  }
  const upd = (id: number, k: 'motivo' | 'nota', v: string) => setDec({ ...dec, [id]: { ...(dec[id] ?? { motivo: '', nota: '' }), [k]: v } })

  return (
    <>
      {res && (
        <div className="kpis k3">
          <div className="kpi"><div className="kpi-label">Pendientes</div><div className="kpi-value">{res.pendientes}</div></div>
          <div className="kpi"><div className="kpi-label">Reportes de seguridad</div><div className="kpi-value">{res.pendientes_seguridad}</div>
            <div className={`kpi-delta ${res.pendientes_seguridad ? 'down' : 'up'}`}>{res.pendientes_seguridad ? '▲ atender primero' : 'sin pendientes'}</div></div>
          <div className="kpi"><div className="kpi-label">Decididos hoy</div><div className="kpi-value">{res.decididos_hoy}</div></div>
        </div>
      )}
      <Card title="Cola de moderación" sub="Los reportes de seguridad (amenazas, fraude, evasión de la plataforma) aparecen primero">
        <div className="filters">
          <div className="seg">{[['pendiente', 'Pendientes'], ['aprobado', 'Aprobados'], ['rechazado', 'Rechazados']].map(([k, l]) =>
            <button key={k} className={f.estado === k ? 'on' : ''} onClick={() => setF({ ...f, estado: k, page: 1 })}>{l}</button>)}</div>
          <select value={f.tipo} onChange={e => setF({ ...f, tipo: e.target.value, page: 1 })} aria-label="Tipo">
            <option value="">Todos los tipos</option>{Object.entries(TIPOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </div>
        <ErrorBox error={error} />
        {!data ? <Cargando /> : (
          <>
            {data.items.map(el => {
              const d = dec[el.id_elemento] ?? { motivo: '', nota: '' }
              return (
                <article key={el.id_elemento} className={`mod-item${el.es_reporte_seguridad ? ' seg' : ''}`}>
                  <div className="chips">
                    {el.es_reporte_seguridad && <span className="chip crit">⚠ Seguridad</span>}
                    <span className="chip neutral">{TIPOS[el.tipo_elemento]}</span>
                    {el.motivo_reporte && <span className="chip info">Reporte: {el.motivo_reporte}</span>}
                    <Chip estado={el.estado} />
                    <span className="muted small" style={{ marginLeft: 'auto' }}>{hace(el.fecha_creacion)}</span>
                  </div>
                  <blockquote className="mod-quote">{el.contenido_reportado}</blockquote>
                  <div className="small muted">
                    Autor: <b>{el.autor}</b>{el.autor_rechazos_90d > 0 && <span className="chip sm serious" style={{ marginLeft: 6 }}>{el.autor_rechazos_90d} rechazo(s) en 90 d</span>}
                    {el.reportante && <> · Reportado por {el.reportante}</>}
                  </div>
                  {el.estado !== 'pendiente' && (
                    <div className="small" style={{ marginTop: 6 }}>Decidido por {el.decisor} · {fechaHora(el.fecha_decision)}
                      {el.motivo_rechazo && <> · motivo: <b>{MOTIVOS[el.motivo_rechazo] ?? el.motivo_rechazo}</b></>}{el.nota_decision && <> · «{el.nota_decision}»</>}</div>
                  )}
                  {escribe && el.estado === 'pendiente' && (
                    <div className="mod-form">
                      <select value={d.motivo} onChange={e => upd(el.id_elemento, 'motivo', e.target.value)} aria-label="Motivo de rechazo">
                        <option value="">Motivo de rechazo…</option>{Object.entries(MOTIVOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
                      <input placeholder="Nota interna (opcional, obligatoria si el motivo es «otro»)" value={d.nota} onChange={e => upd(el.id_elemento, 'nota', e.target.value)} aria-label="Nota" />
                      <button className="btn primary sm" onClick={() => decidir(el, 'aprobado')}>✔ Aprobar</button>
                      <button className="btn ghost sm danger" disabled={!d.motivo || (d.motivo === 'otro' && !d.nota.trim())} onClick={() => decidir(el, 'rechazado')}>✖ Rechazar</button>
                    </div>
                  )}
                </article>
              )
            })}
            {!data.items.length && <p className="empty">La cola está vacía. ✔</p>}
            <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={p => setF({ ...f, page: p })} />
          </>
        )}
      </Card>
    </>
  )
}
