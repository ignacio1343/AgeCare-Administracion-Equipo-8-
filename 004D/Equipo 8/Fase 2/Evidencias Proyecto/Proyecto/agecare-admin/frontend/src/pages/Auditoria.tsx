import { useEffect, useState } from 'react'
import { api, type Auditoria as A, type Page } from '../api'
import { Card, Cargando, ErrorBox, fechaHora, Paginacion } from '../components/ui'

const GRUPOS = [['', 'Todas'], ['auth.', 'Sesiones'], ['staff.', 'Staff'], ['ticket.', 'Tickets']]

function Valor({ json }: { json: string | null }) {
  if (!json) return <span className="muted">—</span>
  try {
    const o = JSON.parse(json)
    if (o && typeof o === 'object') return <>{Object.entries(o).map(([k, v]) => <div key={k}><span className="muted">{k}:</span> {String(v)}</div>)}</>
  } catch { /* texto plano */ }
  return <>{json}</>
}

// CU04 · Consultar bitácora de auditoría (OE4: trazabilidad del 100% de las acciones)
export default function Auditoria() {
  const [data, setData] = useState<Page<A> | null>(null)
  const [accion, setAccion] = useState('')
  const [page, setPage] = useState(1)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    api<Page<A>>('/auditoria', { query: { accion, page, page_size: 25 } }).then(setData).catch(setError)
  }, [accion, page])

  return (
    <Card title="Bitácora de auditoría" sub="Registro inmutable: la API solo permite agregar eventos, nunca editarlos ni borrarlos">
      <div className="filters">
        <div className="seg">{GRUPOS.map(([k, l]) => <button key={k} className={accion === k ? 'on' : ''} onClick={() => { setAccion(k); setPage(1) }}>{l}</button>)}</div>
      </div>
      <ErrorBox error={error} />
      {!data ? <Cargando /> : (
        <>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Fecha</th><th>Actor</th><th>Acción</th><th>Entidad</th><th>Antes</th><th>Después</th><th>IP</th></tr></thead>
            <tbody>
              {data.items.map(r => (
                <tr key={r.id_registro}>
                  <td className="nowrap">{fechaHora(r.fecha_hora)}</td>
                  <td>{r.actor_nombre ?? <span className="muted">Sistema / anónimo</span>}</td>
                  <td><code>{r.accion}</code></td>
                  <td>{r.tipo_entidad}{r.id_entidad && <span className="muted"> #{r.id_entidad}</span>}</td>
                  <td className="small"><Valor json={r.valor_anterior} /></td>
                  <td className="small"><Valor json={r.valor_nuevo} /></td>
                  <td className="mono small">{r.ip ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
          <Paginacion page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
        </>
      )}
    </Card>
  )
}
