// Vista del cuidador: ficha de cada residente asignado con su estado vital (Normal / Alerta / Riesgoso) y observación.
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { fechaHora } from '../components/ui'
import { papi, textoError, type RegistroVital, type Residente } from './api'
import { Cargando } from './PortalApp'
import { ChipEstado, ESTADO_VITAL, hace } from './Representante'

interface Item { residente: Residente; ultimo_estado: RegistroVital | null }
type Estado = 'normal' | 'alerta' | 'riesgoso'
const OPCIONES: [Estado, string, string][] = [
  ['normal', 'Normal', 'Signos y ánimo habituales'], ['alerta', 'Alerta', 'Algo fuera de lo normal: hay que vigilar'],
  ['riesgoso', 'Riesgoso', 'Requiere atención: se avisa a la familia'],
]

export default function Cuidador() {
  const [items, setItems] = useState<Item[] | null>(null)
  const [sel, setSel] = useState<number | null>(null)
  const [error, setError] = useState('')
  const cargar = useCallback(() => papi<Item[]>('/cuidador/residentes').then(xs => { setItems(xs); setSel(s => s ?? xs[0]?.residente.id_paciente ?? null) })
    .catch(e => setError(textoError(e))), [])
  useEffect(() => { cargar() }, [cargar])
  if (!items) return error ? <div className="p-alerta crit">{error}</div> : <Cargando />
  const actual = items.find(i => i.residente.id_paciente === sel)
  return (
    <>
      <div className="p-titulo"><div><h1>Ficha de residentes</h1><p className="p-sub">Registra el estado vital y una observación. Queda guardado con tu nombre y la hora.</p></div></div>
      {items.length === 0 && <section className="p-tarjeta p-vacio"><p>No tienes residentes asignados. Pide a soporte que te los asigne.</p></section>}
      <div className="p-cuidador">
        <nav className="p-lista-res" aria-label="Residentes asignados">
          {items.map(i => (
            <button key={i.residente.id_paciente} className={i.residente.id_paciente === sel ? 'on' : ''} onClick={() => setSel(i.residente.id_paciente)}>
              <b>{i.residente.nombre}</b>
              <small>{i.ultimo_estado ? <><ChipEstado r={i.ultimo_estado} /> {hace(i.ultimo_estado.fecha)}</> : 'Sin registros'}</small>
            </button>
          ))}
        </nav>
        {actual && <Ficha key={actual.residente.id_paciente} item={actual} alGuardar={cargar} />}
      </div>
    </>
  )
}

function Ficha({ item, alGuardar }: { item: Item; alGuardar: () => void }) {
  const id = item.residente.id_paciente
  const [estado, setEstado] = useState<Estado | null>(null)
  const [obs, setObs] = useState('')
  const [hist, setHist] = useState<RegistroVital[]>([])
  const [msg, setMsg] = useState<{ cls: string; txt: string } | null>(null)
  const [enviando, setEnviando] = useState(false)
  const cargarHist = useCallback(() => { papi<RegistroVital[]>(`/cuidador/residentes/${id}/historial`).then(setHist).catch(() => {}) }, [id])
  useEffect(() => { cargarHist() }, [cargarHist])

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    if (!estado) return
    setEnviando(true); setMsg(null)
    try {
      const r = await papi<{ mensaje: string }>(`/cuidador/residentes/${id}/ficha`, { method: 'POST', body: { estado, observacion: obs } })
      setMsg({ cls: estado === 'riesgoso' ? 'crit' : 'ok', txt: r.mensaje })
      setEstado(null); setObs(''); cargarHist(); alGuardar()
    } catch (x) { setMsg({ cls: 'crit', txt: textoError(x) }) } finally { setEnviando(false) }
  }
  return (
    <div className="p-ficha">
      <section className="p-tarjeta">
        <h2>{item.residente.nombre}</h2>
        <p className="p-sub">{item.residente.edad ? `${item.residente.edad} años · ` : ''}RUT {item.residente.rut ?? '—'}</p>
        <form onSubmit={guardar} className="p-form">
          <fieldset className="p-semaforo">
            <legend>Estado vital</legend>
            {OPCIONES.map(([v, t, d]) => (
              <label key={v} className={`${ESTADO_VITAL[v].cls}${estado === v ? ' sel' : ''}`}>
                <input type="radio" name="estado" value={v} checked={estado === v} onChange={() => setEstado(v)} />
                <span className="p-sem-ico">{ESTADO_VITAL[v].ico}</span><b>{t}</b><small>{d}</small>
              </label>
            ))}
          </fieldset>
          <label className="p-campo"><span>Observación</span>
            <textarea value={obs} onChange={e => setObs(e.target.value)} rows={3} minLength={3} maxLength={1000} required
                      placeholder="Ej.: Presión 150/90, algo mareada. Se controla de nuevo en 2 horas." /></label>
          {estado === 'riesgoso' && <div className="p-alerta crit">Al guardar se avisa de inmediato a la familia por WhatsApp y en su portal (planes Dorado, Platino y Proveedor).</div>}
          {msg && <div className={`p-alerta ${msg.cls}`} role="status">{msg.txt}</div>}
          <button className={`p-btn grande ${estado === 'riesgoso' ? 'peligro-lleno' : 'primario'}`} disabled={!estado || obs.trim().length < 3 || enviando}>
            {enviando ? 'Guardando…' : estado === 'riesgoso' ? 'Guardar y avisar a la familia' : 'Guardar en la ficha'}</button>
        </form>
      </section>
      <section className="p-tarjeta">
        <h2>Historial</h2>
        {hist.length === 0 ? <p className="p-muted">Sin registros todavía.</p> : (
          <ol className="p-historial">
            {hist.map(r => <li key={r.id_registro}><ChipEstado r={r} /><div><p>{r.observacion}</p><small>{r.cuidador} · {fechaHora(r.fecha)}</small></div></li>)}
          </ol>
        )}
      </section>
    </div>
  )
}
