import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Ref, type Respuesta, type TicketDetalle as TD } from '../api'
import { useAuth } from '../auth'
import { Card, CANALES, Cargando, ErrorBox, EstadoChip, ESTADOS, fecha, fechaHora, PERFILES, PrioridadChip, PRIORIDADES } from '../components/ui'

const ACCION: Record<string, string> = {
  en_curso: 'Tomar ticket', esperando_usuario: 'Esperar al usuario', resuelto: 'Marcar resuelto', cerrado: 'Cerrar',
}
const etiqueta = (desde: string, hacia: string) =>
  hacia === 'en_curso' && desde === 'resuelto' ? 'Reabrir' : hacia === 'en_curso' && desde === 'esperando_usuario' ? 'Retomar' : ACCION[hacia] ?? ESTADOS[hacia]?.label

// CU37 Atender ticket · CU38 Contexto del solicitante · CU39 Responder · CU40 Encuesta
export default function TicketDetalle() {
  const { id } = useParams()
  const { puede } = useAuth()
  const escribe = puede('soporte', 'escritura')
  const [t, setT] = useState<TD | null>(null)
  const [resp, setResp] = useState<Respuesta[]>([])
  const [agentes, setAgentes] = useState<Ref[]>([])
  const [cats, setCats] = useState<Ref[]>([])
  const [error, setError] = useState<unknown>(null)
  const [cuerpo, setCuerpo] = useState('')
  const [interna, setInterna] = useState(false)
  const [ocupado, setOcupado] = useState(false)

  const cargar = useCallback(async () => {
    const [d, r] = await Promise.all([api<TD>(`/soporte/tickets/${id}`), api<Respuesta[]>(`/soporte/tickets/${id}/respuestas`)])
    setT(d); setResp(r)
  }, [id])

  useEffect(() => {
    cargar().catch(setError)
    api<Ref[]>('/soporte/agentes').then(setAgentes).catch(() => {})
    api<Ref[]>('/soporte/categorias').then(setCats).catch(() => {})
  }, [cargar])

  const patch = async (body: Record<string, unknown>) => {
    setError(null); setOcupado(true)
    try { await api(`/soporte/tickets/${id}`, { method: 'PATCH', body }); await cargar() } catch (e) { setError(e) } finally { setOcupado(false) }
  }
  const responder = async (e: FormEvent) => {
    e.preventDefault()
    setError(null); setOcupado(true)
    try {
      await api(`/soporte/tickets/${id}/respuestas`, { method: 'POST', body: { cuerpo, es_interna: interna } })
      setCuerpo(''); setInterna(false); await cargar()
    } catch (err) { setError(err) } finally { setOcupado(false) }
  }

  if (!t) return error ? <ErrorBox error={error} /> : <Cargando />
  const cerrado = t.estado === 'cerrado'

  return (
    <>
      <div className="ticket-head">
        <Link to="/soporte" className="btn link">‹ Volver a la cola</Link>
        <h2><span className="mono muted">#{t.numero}</span> {t.asunto}</h2>
        <div className="chips"><EstadoChip estado={t.estado} /><PrioridadChip prioridad={t.prioridad} />
          <span className="chip neutral">{t.categoria.nombre}</span><span className="chip neutral">Canal: {CANALES[t.canal]}</span></div>
      </div>
      <ErrorBox error={error} />
      <div className="grid ticket-grid">
        <div>
          <Card title="Descripción" sub={`Recibido ${fechaHora(t.fecha_creacion)}`}><p className="pre">{t.descripcion}</p></Card>
          <Card title="Conversación" sub={`${resp.length} mensajes · las notas internas no las ve el usuario`}>
            <ol className="thread">
              {resp.map(r => (
                <li key={r.id_respuesta} className={`msg ${r.tipo_autor}${r.es_interna ? ' interna' : ''}`}>
                  <div className="msg-head"><b>{r.autor_nombre}</b>
                    {r.es_interna && <span className="chip warn sm">Nota interna</span>}
                    <span className="muted">{fechaHora(r.fecha)}</span></div>
                  <p className="pre">{r.cuerpo}</p>
                </li>
              ))}
              {!resp.length && <li className="muted">Aún no hay mensajes.</li>}
            </ol>
            {escribe && !cerrado && (
              <form onSubmit={responder} className="reply">
                <textarea rows={4} value={cuerpo} onChange={e => setCuerpo(e.target.value)} maxLength={8000}
                  placeholder={interna ? 'Nota interna para el equipo…' : 'Respuesta para el usuario (se le notifica por correo y push)…'} aria-label="Mensaje" />
                <div className="reply-bar">
                  <label className="toggle"><input type="checkbox" checked={interna} onChange={e => setInterna(e.target.checked)} /> Nota interna</label>
                  <button className="btn primary" disabled={!cuerpo.trim() || ocupado}>{interna ? 'Guardar nota' : 'Enviar respuesta'}</button>
                </div>
              </form>
            )}
            {cerrado && <div className="alert neutral">El ticket está cerrado y no admite nuevas respuestas.</div>}
          </Card>
        </div>
        <div>
          {escribe && (
            <Card title="Atender">
              <div className="state-actions">
                {t.transiciones_permitidas.map(s => (
                  <button key={s} className={`btn ${s === 'resuelto' ? 'primary' : 'ghost'} sm`} disabled={ocupado} onClick={() => patch({ estado: s })}>
                    {etiqueta(t.estado, s)}
                  </button>
                ))}
                {!t.transiciones_permitidas.length && <span className="muted">Sin acciones de estado disponibles.</span>}
              </div>
              <label className="stack">Asignado a
                <select value={String(t.asignado?.id ?? '')} disabled={ocupado || cerrado} onChange={e => patch({ id_staff_asignado: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">Sin asignar</option>{agentes.map(a => <option key={a.id} value={a.id}>{a.nombre}</option>)}
                </select></label>
              <label className="stack">Prioridad
                <select value={t.prioridad} disabled={ocupado || cerrado} onChange={e => patch({ prioridad: e.target.value })}>
                  {Object.entries(PRIORIDADES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select></label>
              <label className="stack">Categoría
                <select value={t.categoria.id} disabled={ocupado || cerrado} onChange={e => patch({ codigo_categoria: e.target.value })}>
                  {cats.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                </select></label>
            </Card>
          )}
          <Card title="Solicitante" sub="CU38 · contexto desde la plataforma AgeCare">
            <dl className="kv">
              <dt>Nombre</dt><dd>{t.solicitante.nombre}</dd>
              <dt>Correo</dt><dd>{t.solicitante.email ?? '—'}</dd>
              {t.solicitante.id_usuario ? (<>
                <dt>Perfil</dt><dd>{t.solicitante.perfiles.map(p => PERFILES[p] ?? p).join(', ')}</dd>
                <dt>Cuenta</dt><dd>{t.contexto.estado_cuenta} · desde {fecha(t.contexto.fecha_registro)}</dd>
                <dt>Último acceso</dt><dd>{fechaHora(t.contexto.ultimo_acceso)}</dd>
                <dt>Pacientes</dt><dd>{t.contexto.pacientes.map(p => <div key={p.id}>{p.nombre}</div>)}{!t.contexto.pacientes.length && '—'}</dd>
                <dt>Tickets previos</dt><dd>{t.contexto.tickets_previos}</dd>
              </>) : (<><dt>Cuenta</dt><dd className="muted">Sin cuenta enlazada en la app</dd></>)}
              {t.paciente && (<><dt>Paciente del caso</dt><dd>{t.paciente.nombre}</dd></>)}
            </dl>
          </Card>
          <Card title="Tiempos">
            <dl className="kv">
              <dt>Creado</dt><dd>{fechaHora(t.fecha_creacion)}</dd>
              <dt>Primera respuesta</dt><dd>{fechaHora(t.fecha_primera_respuesta)}</dd>
              <dt>Resuelto</dt><dd>{fechaHora(t.fecha_resolucion)}</dd>
              <dt>Cerrado</dt><dd>{fechaHora(t.fecha_cierre)}</dd>
            </dl>
          </Card>
          {t.encuesta && (
            <Card title="Encuesta de satisfacción" sub={`CU40 · enviada ${fechaHora(t.encuesta.fecha_envio)}`}>
              {t.encuesta.puntaje ? (
                <><div className="stars" aria-label={`${t.encuesta.puntaje} de 5`}>{'★'.repeat(t.encuesta.puntaje)}<span className="muted">{'★'.repeat(5 - t.encuesta.puntaje)}</span></div>
                  {t.encuesta.comentario && <p>“{t.encuesta.comentario}”</p>}</>
              ) : <p className="muted">El usuario aún no responde.</p>}
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
