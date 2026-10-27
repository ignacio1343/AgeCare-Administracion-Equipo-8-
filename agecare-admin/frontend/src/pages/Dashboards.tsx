import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { LineChart, rampa } from '../components/charts'
import { Card, Cargando, clp, Delta, ErrorBox, fecha, num, pct } from '../components/ui'

interface Kpi { valor: number; anterior: number | null; variacion: number | null }
interface Comercial {
  periodo: string; desde: string; hasta: string; descargas: Kpi; altas: Kpi; bajas: Kpi; usuarios_activos: Kpi; usuarios_pago: Kpi; mrr: Kpi
  churn_periodo: number; serie_etiquetas: string[]; serie_altas: number[]; serie_bajas: number[]; actualizado: string | null
}
interface Planes { fecha: string | null; total_usuarios: number; total_mrr: number
  planes: { codigo_plan: string; nombre: string; unidad_facturable: string; usuarios: number; cuota: number; precio: number | null; mrr: number; churn_mensual: number }[] }
interface Embudo { fecha: string | null; conversion_pago: number; conversion_pago_hace_30d: number | null
  pasos: { etapa: string; valor: number; sobre_descargas: number; sobre_anterior: number | null }[] }
interface PerfilM { codigo_perfil: string; nombre: string; usuarios_activos: number; sesiones_semana: number; duracion_media_seg: number; retencion_30d: number }
interface Adopcion { ventana_dias: number; perfiles: { codigo: string; nombre: string }[]
  filas: { codigo_funcionalidad: string; nombre: string; uso_bajo_esperado: boolean; nota: string | null; celdas: { codigo_perfil: string; adopcion: number | null; usuarios: number | null }[] }[]
  alertas: { funcionalidad: string; perfil: string; adopcion: number }[] }
interface SoporteSerie { fechas: string[]; creados: number[]; resueltos: number[]; primera_respuesta_h: (number | null)[]; csat: (number | null)[] }

const PERIODOS: [string, string][] = [['7d', '7 días'], ['30d', '30 días'], ['mes', 'Mes actual'], ['ytd', 'Año'], ['12m', '12 meses']]
const corta = (s: string) => new Date(s + 'T12:00:00').toLocaleDateString('es-CL', { day: 'numeric', month: 'short' })

// CU21 Métricas comerciales · CU22 Embudo · CU23 Perfiles · CU24 Adopción · CU25 Soporte · CU26 Consolidar
export default function Dashboards() {
  const { puede } = useAuth()
  const [periodo, setPeriodo] = useState('30d')
  const [ventana, setVentana] = useState(30)
  const [com, setCom] = useState<Comercial | null>(null)
  const [pl, setPl] = useState<Planes | null>(null)
  const [emb, setEmb] = useState<Embudo | null>(null)
  const [per, setPer] = useState<PerfilM[] | null>(null)
  const [ad, setAd] = useState<Adopcion | null>(null)
  const [sop, setSop] = useState<SoporteSerie | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [aviso, setAviso] = useState('')

  useEffect(() => { api<Comercial>('/metricas/comerciales', { query: { periodo } }).then(setCom).catch(setError) }, [periodo])
  useEffect(() => {
    api<PerfilM[]>('/metricas/perfiles', { query: { ventana } }).then(setPer).catch(setError)
    api<Adopcion>('/metricas/adopcion', { query: { ventana } }).then(setAd).catch(setError)
  }, [ventana])
  const cargarFijos = () => {
    api<Planes>('/metricas/planes').then(setPl).catch(setError)
    api<Embudo>('/metricas/embudo').then(setEmb).catch(setError)
    api<SoporteSerie>('/metricas/soporte', { query: { dias: 30 } }).then(setSop).catch(setError)
  }
  useEffect(cargarFijos, [])

  const consolidar = async () => {
    setError(null)
    try { await api('/metricas/consolidar', { method: 'POST' }); setAviso('Métricas consolidadas.'); cargarFijos() } catch (e) { setError(e) }
  }

  const maxPlan = Math.max(1, ...(pl?.planes.map(p => p.usuarios) ?? [1]))
  return (
    <>
      <div className="filters" style={{ justifyContent: 'space-between' }}>
        <div className="seg" role="tablist" aria-label="Periodo">
          {PERIODOS.map(([k, l]) => <button key={k} className={periodo === k ? 'on' : ''} onClick={() => setPeriodo(k)}>{l}</button>)}
        </div>
        <div className="filters" style={{ margin: 0 }}>
          {com && <span className="muted small">{fecha(com.desde)} – {fecha(com.hasta)} · actualizado {fecha(com.actualizado)}</span>}
          {puede('metricas', 'escritura') && <button className="btn ghost sm" onClick={consolidar}>Consolidar ahora</button>}
        </div>
      </div>
      <ErrorBox error={error} />
      {aviso && <div className="alert ok">{aviso}</div>}

      {!com ? <Cargando /> : (
        <div className="kpis k6">
          <div className="kpi"><div className="kpi-label">Descargas</div><div className="kpi-value">{num(com.descargas.valor)}</div><Delta v={com.descargas.variacion} /></div>
          <div className="kpi"><div className="kpi-label">Altas (cuentas nuevas)</div><div className="kpi-value">{num(com.altas.valor)}</div><Delta v={com.altas.variacion} /></div>
          <div className="kpi"><div className="kpi-label">Bajas</div><div className="kpi-value">{num(com.bajas.valor)}</div><Delta v={com.bajas.variacion} invertir />
            <div className="kpi-note">Churn del periodo {pct(com.churn_periodo, 2)}</div></div>
          <div className="kpi"><div className="kpi-label">Usuarios activos</div><div className="kpi-value">{num(com.usuarios_activos.valor)}</div><Delta v={com.usuarios_activos.variacion} /></div>
          <div className="kpi"><div className="kpi-label">Usuarios de pago</div><div className="kpi-value">{num(com.usuarios_pago.valor)}</div><Delta v={com.usuarios_pago.variacion} /></div>
          <div className="kpi"><div className="kpi-label">MRR</div><div className="kpi-value">{clp(com.mrr.valor)}</div><Delta v={com.mrr.variacion} /></div>
        </div>
      )}

      <div className="grid split">
        <Card title="Altas y bajas" sub={com && com.serie_etiquetas.length > 40 ? 'Totales por semana' : 'Totales por día'}>
          {com ? <LineChart etiquetas={com.serie_etiquetas} series={[{ nombre: 'Altas', valores: com.serie_altas }, { nombre: 'Bajas', valores: com.serie_bajas }]} /> : <Cargando />}
        </Card>
        <Card title="Mezcla de planes" sub={pl ? `${num(pl.total_usuarios)} usuarios · MRR ${clp(pl.total_mrr)}` : ''}>
          {!pl ? <Cargando /> : (
            <>
              <div className="bars">
                {pl.planes.map(p => (
                  <div className="bar-row" key={p.codigo_plan} style={{ gridTemplateColumns: '90px 1fr 92px' }} title={`${p.nombre}: ${num(p.usuarios)} (${pct(p.cuota)})`}>
                    <span className="bar-label">{p.nombre}</span>
                    <span className="bar-track"><span className="bar" style={{ width: `${(p.usuarios / maxPlan) * 100}%` }} /></span>
                    <span className="bar-val">{num(p.usuarios)} <span className="muted">· {pct(p.cuota)}</span></span>
                  </div>
                ))}
              </div>
              <div className="table-wrap" style={{ marginTop: 12 }}><table className="data">
                <thead><tr><th>Plan</th><th className="right">Precio</th><th className="right">MRR</th><th className="right">Churn mes</th></tr></thead>
                <tbody>{pl.planes.map(p => <tr key={p.codigo_plan}><td>{p.nombre}<div className="sub">por {p.unidad_facturable}</div></td>
                  <td className="right">{clp(p.precio)}</td><td className="right">{clp(p.mrr)}</td><td className="right">{pct(p.churn_mensual)}</td></tr>)}</tbody>
              </table></div>
            </>
          )}
        </Card>
      </div>

      <div className="grid g2">
        <Card title="Embudo freemium" sub={emb ? `CU22 · conversión a pago ${pct(emb.conversion_pago, 2)} (hace 30 d: ${pct(emb.conversion_pago_hace_30d, 2)})` : ''}>
          {!emb ? <Cargando /> : (
            <div className="funnel">
              {emb.pasos.map(p => (
                <div className="funnel-row" key={p.etapa}>
                  <span>{p.etapa}</span>
                  <span className="bar-track" style={{ height: 22 }}><span className="funnel-bar" style={{ display: 'block', width: `${p.sobre_descargas * 100}%` }} /></span>
                  <span className="v"><b>{num(p.valor)}</b><small>{p.sobre_anterior != null ? `${pct(p.sobre_anterior)} del paso anterior` : 'base'}</small></span>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title="Soporte · últimos 30 días" sub="Tickets creados y resueltos por día (seguimiento de OE1)">
          {sop ? <LineChart etiquetas={sop.fechas.map(corta)} series={[{ nombre: 'Creados', valores: sop.creados }, { nombre: 'Resueltos', valores: sop.resueltos }]} alto={200} /> : <Cargando />}
        </Card>
      </div>

      <div className="filters">
        <span className="muted small">Ventana para perfiles y adopción:</span>
        <div className="seg">{[7, 30, 90].map(v => <button key={v} className={ventana === v ? 'on' : ''} onClick={() => setVentana(v)}>{v} días</button>)}</div>
      </div>
      <Card title="Uso por perfil" sub="CU23 · actividad de cada tipo de usuario de la app">
        {!per ? <Cargando /> : (
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Perfil</th><th className="right">Usuarios activos</th><th className="right">Sesiones / semana</th><th className="right">Duración media</th><th className="right">Retención 30 d</th></tr></thead>
            <tbody>{per.map(p => <tr key={p.codigo_perfil}><td className="strong">{p.nombre}</td><td className="right">{num(p.usuarios_activos)}</td>
              <td className="right">{num(p.sesiones_semana, 1)}</td><td className="right">{Math.floor(p.duracion_media_seg / 60)} min {p.duracion_media_seg % 60} s</td>
              <td className="right">{pct(p.retencion_30d, 0)}</td></tr>)}</tbody>
          </table></div>
        )}
      </Card>
      <Card title="Adopción de funcionalidades por perfil" sub="CU24 · % de usuarios activos del perfil que usó la función · celdas rayadas = no aplica al perfil">
        {!ad ? <Cargando /> : (
          <>
            {ad.alertas.length > 0 && (
              <div className="alert neutral" style={{ margin: '0 0 12px' }}>▲ <b>Adopción bajo 15%:</b> {ad.alertas.slice(0, 5).map(a => `${a.funcionalidad} (${a.perfil}, ${pct(a.adopcion, 0)})`).join(' · ')}{ad.alertas.length > 5 && ` y ${ad.alertas.length - 5} más`}</div>
            )}
            <div className="table-wrap"><table className="data heat">
              <thead><tr><th>Funcionalidad</th>{ad.perfiles.map(p => <th key={p.codigo} style={{ textAlign: 'center' }}>{p.nombre}</th>)}</tr></thead>
              <tbody>{ad.filas.map(f => (
                <tr key={f.codigo_funcionalidad}>
                  <td><div>{f.nombre}</div>{f.uso_bajo_esperado && <div className="sub">uso bajo esperado{f.nota ? ` · ${f.nota}` : ''}</div>}</td>
                  {f.celdas.map(c => {
                    if (c.adopcion == null) return <td key={c.codigo_perfil} className="cell na" title="No aplica">—</td>
                    const r = rampa(c.adopcion)
                    return <td key={c.codigo_perfil} className="cell" style={{ background: r.bg, color: r.claro ? '#fff' : '#1f2733', borderBottom: '2px solid #fff' }}
                      title={`${f.nombre} · ${ad.perfiles.find(p => p.codigo === c.codigo_perfil)?.nombre}: ${pct(c.adopcion, 0)} (${num(c.usuarios)} usuarios)`}>{pct(c.adopcion, 0)}</td>
                  })}
                </tr>
              ))}</tbody>
            </table></div>
          </>
        )}
      </Card>
    </>
  )
}
