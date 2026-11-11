// «Mis solicitudes»: tickets del usuario (y de sus residentes si es representante), conversación con soporte,
// respuesta del usuario y encuesta de satisfacción (CU57 y CU40).
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { fechaHora } from '../components/ui'
import { papi, textoError } from './api'
import { Cargando } from './PortalApp'

interface Solicitud {
  numero: number; asunto: string; categoria: string; estado: string; estado_texto: string; fecha_creacion: string
  fecha_actualizacion: string; solicitante: string; es_mia: boolean; residente: string | null
  respuestas_soporte: number; encuesta_pendiente: boolean
}
interface Mensaje { autor: string; de_soporte: boolean; cuerpo: string; fecha: string }
interface Detalle extends Solicitud {
  descripcion: string; conversacion: Mensaje[]; puede_responder: boolean
  encuesta: { puntaje: number | null; comentario: string | null; fecha_respuesta: string | null } | null
}

const CLASE: Record<string, string> = { abierto: 'neutral', en_curso: 'info', esperando_usuario: 'warn', resuelto: 'ok', cerrado: 'neutral' }

function Estado({ s }: { s: Solicitud }) {
  return <span className={`p-chip ${CLASE[s.estado] === 'ok' ? 'ok' : CLASE[s.estado] === 'warn' ? 'warn' : 'p-chip-gris'}`}>{s.estado_texto}</span>
}

export function MisSolicitudes() {
  const [items, setItems] = useState<Solicitud[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { papi<Solicitud[]>('/solicitudes').then(setItems).catch(e => setError(textoError(e))) }, [])
  if (!items) return error ? <div className="p-alerta crit">{error}</div> : <Cargando />
  return (
    <>
      <div className="p-titulo">
        <div><h1>Mis solicitudes</h1><p className="p-sub">Lo que le pediste al equipo de soporte y sus respuestas.</p></div>
        <Link to="/portal/ayuda" className="p-btn primario">＋ Nueva solicitud</Link>
      </div>
      {items.length === 0 ? (
        <section className="p-tarjeta p-vacio"><div className="p-vacio-ico">📨</div><h2>No tienes solicitudes</h2>
          <p>Si necesitas ayuda, escríbenos y te responderemos aquí.</p>
          <Link to="/portal/ayuda" className="p-btn primario grande">Pedir ayuda</Link></section>
      ) : (
        <div className="p-solicitudes">
          {items.map(s => (
            <Link key={s.numero} to={`/portal/solicitudes/${s.numero}`} className={`p-solicitud${s.encuesta_pendiente || s.estado === 'esperando_usuario' ? ' destacada' : ''}`}>
              <div className="p-sol-head"><span className="mono p-muted">#{s.numero}</span><Estado s={s} /></div>
              <b>{s.asunto}</b>
              <small>
                {s.es_mia ? 'Tu solicitud' : `Solicitud de ${s.solicitante}`} · {s.categoria} · actualizada {fechaHora(s.fecha_actualizacion)}
              </small>
              {s.respuestas_soporte > 0 && <small className="p-sol-resp">💬 {s.respuestas_soporte} respuesta{s.respuestas_soporte > 1 ? 's' : ''} de soporte</small>}
              {s.estado === 'esperando_usuario' && <small className="p-sol-aviso">Soporte espera tu respuesta</small>}
              {s.encuesta_pendiente && <small className="p-sol-aviso">⭐ Califica la atención</small>}
            </Link>
          ))}
        </div>
      )}
    </>
  )
}

export function VerSolicitud() {
  const { numero } = useParams()
  const [d, setD] = useState<Detalle | null>(null)
  const [error, setError] = useState('')
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [estrellas, setEstrellas] = useState(0)
  const [comentario, setComentario] = useState('')
  const cargar = useCallback(() => papi<Detalle>(`/solicitudes/${numero}`).then(setD).catch(e => setError(textoError(e))), [numero])
  useEffect(() => { cargar(); const t = setInterval(cargar, 30_000); return () => clearInterval(t) }, [cargar])

  const responder = async (e: FormEvent) => {
    e.preventDefault()
    setEnviando(true); setError('')
    try { setD(await papi<Detalle>(`/solicitudes/${numero}/respuestas`, { method: 'POST', body: { cuerpo: texto } })); setTexto('') }
    catch (x) { setError(textoError(x)) } finally { setEnviando(false) }
  }
  const calificar = async () => {
    setError('')
    try { setD(await papi<Detalle>(`/solicitudes/${numero}/encuesta`, { method: 'POST', body: { puntaje: estrellas, comentario: comentario || null } })) }
    catch (x) { setError(textoError(x)) }
  }
  if (!d) return error ? <><div className="p-alerta crit">{error}</div><Link to="/portal/solicitudes" className="p-volver">← Mis solicitudes</Link></> : <Cargando />
  return (
    <>
      <Link to="/portal/solicitudes" className="p-volver arriba">← Mis solicitudes</Link>
      <div className="p-titulo"><div>
        <h1><span className="mono p-muted">#{d.numero}</span> {d.asunto}</h1>
        <p className="p-sub">{d.es_mia ? 'Tu solicitud' : `Solicitud de ${d.solicitante}`} · {d.categoria} · enviada {fechaHora(d.fecha_creacion)}</p>
      </div><Estado s={d} /></div>
      {error && <div className="p-alerta crit">{error}</div>}

      {d.encuesta_pendiente && (
        <section className="p-tarjeta p-encuesta">
          <h2>¿Cómo te atendimos?</h2>
          <p className="p-sub">Soporte marcó esta solicitud como resuelta. Tu opinión nos ayuda a mejorar.</p>
          <div className="p-estrellas" role="radiogroup" aria-label="Calificación de 1 a 5">
            {[1, 2, 3, 4, 5].map(n => (
              <button key={n} role="radio" aria-checked={estrellas === n} aria-label={`${n} estrella${n > 1 ? 's' : ''}`}
                      className={n <= estrellas ? 'on' : ''} onClick={() => setEstrellas(n)}>★</button>
            ))}
          </div>
          <textarea className="p-input" rows={2} maxLength={1000} placeholder="Comentario (opcional)" value={comentario} onChange={e => setComentario(e.target.value)} />
          <button className="p-btn primario" disabled={!estrellas} onClick={calificar}>Enviar calificación</button>
        </section>
      )}
      {d.encuesta?.fecha_respuesta && (
        <div className="p-alerta ok">Calificaste la atención con {'★'.repeat(d.encuesta.puntaje ?? 0)}{d.encuesta.comentario ? `: «${d.encuesta.comentario}»` : ''}. ¡Gracias!</div>
      )}

      <section className="p-tarjeta">
        <ol className="p-chat">
          <li className="yo"><div className="p-burbuja"><b>{d.solicitante}</b><p>{d.descripcion}</p><small>{fechaHora(d.fecha_creacion)}</small></div></li>
          {d.conversacion.map((m, i) => (
            <li key={i} className={m.de_soporte ? 'soporte' : 'yo'}>
              <div className="p-burbuja"><b>{m.autor}</b><p>{m.cuerpo}</p><small>{fechaHora(m.fecha)}</small></div>
            </li>
          ))}
          {d.conversacion.every(m => !m.de_soporte) && <li className="p-chat-espera">Soporte aún no responde. Te avisaremos aquí y por correo.</li>}
        </ol>
        {d.puede_responder ? (
          <form onSubmit={responder} className="p-form p-responder">
            <label className="p-campo"><span>{d.estado === 'resuelto' ? '¿Sigue el problema? Escríbenos y la reabrimos' : 'Responder a soporte'}</span>
              <textarea value={texto} onChange={e => setTexto(e.target.value)} rows={3} minLength={2} maxLength={2000} required /></label>
            <button className="p-btn primario" disabled={enviando || texto.trim().length < 2}>{enviando ? 'Enviando…' : 'Enviar'}</button>
          </form>
        ) : <p className="p-muted">Esta solicitud está cerrada. Si necesitas algo más, <Link to="/portal/ayuda">crea una nueva</Link>.</p>}
      </section>
    </>
  )
}
