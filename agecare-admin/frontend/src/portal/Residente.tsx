// Vista del residente (letra grande): chistes, noticias y eventos que publica el equipo AgeCare, y pedir ayuda.
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { papi, textoError, type ContenidoPortal } from './api'
import { usePortal } from './auth'
import { Cargando } from './PortalApp'

type Filtro = '' | 'evento' | 'chiste' | 'noticia'
const FILTROS: [Filtro, string, string][] = [['', 'Todo', '✨'], ['evento', 'Eventos', '📅'], ['chiste', 'Chistes', '😄'], ['noticia', 'Noticias', '📰']]
const ICONO: Record<string, string> = { evento: '📅', chiste: '😄', noticia: '📰' }

interface Inicio { nombre: string; mensaje_bienvenida: string; representantes: string[]; cuidadores: string[] }

function fechaEvento(s: string) {
  const t = new Date(s).toLocaleString('es-CL', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
  return t.charAt(0).toUpperCase() + t.slice(1)
}

export function InicioResidente() {
  const [ini, setIni] = useState<Inicio | null>(null)
  const [filtro, setFiltro] = useState<Filtro>('')
  const [items, setItems] = useState<ContenidoPortal[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { papi<Inicio>('/residente/inicio').then(setIni).catch(e => setError(textoError(e))) }, [])
  useEffect(() => {
    setItems(null)
    papi<ContenidoPortal[]>('/contenidos', { query: { tipo: filtro || undefined } }).then(setItems).catch(e => setError(textoError(e)))
  }, [filtro])
  return (
    <div className="p-residente-vista">
      <section className="p-saludo">
        <h1>¡Hola, {ini?.nombre ?? ''}! 👋</h1>
        <p>{ini?.mensaje_bienvenida}</p>
        {ini && (ini.cuidadores.length > 0 || ini.representantes.length > 0) && (
          <p className="p-circulo">
            {ini.cuidadores.length > 0 && <>Te cuida: <b>{ini.cuidadores.join(', ')}</b>. </>}
            {ini.representantes.length > 0 && <>Tu familiar: <b>{ini.representantes.join(', ')}</b>.</>}
          </p>
        )}
      </section>
      <nav className="p-filtros" aria-label="Tipo de contenido">
        {FILTROS.map(([f, t, i]) => <button key={t} className={filtro === f ? 'on' : ''} onClick={() => setFiltro(f)}><span>{i}</span>{t}</button>)}
      </nav>
      {error && <div className="p-alerta crit">{error}</div>}
      {!items ? <Cargando /> : items.length === 0 ? <p className="p-vacio-txt">No hay publicaciones por ahora. ¡Vuelve pronto!</p> : (
        <div className="p-contenidos">
          {items.map(c => (
            <article key={c.id_contenido} className={`p-contenido ${c.tipo}`}>
              <span className="p-tipo">{ICONO[c.tipo]} {c.tipo === 'evento' ? 'Evento' : c.tipo === 'chiste' ? 'Chiste' : 'Noticia'}</span>
              <h2>{c.titulo}</h2>
              {c.tipo === 'evento' && c.fecha_evento && <p className="p-cuando">🗓 {fechaEvento(c.fecha_evento)}{c.lugar ? ` · 📍 ${c.lugar}` : ''}</p>}
              <p>{c.cuerpo}</p>
            </article>
          ))}
        </div>
      )}
      <section className="p-tarjeta p-ayuda-cta">
        <div><h2>¿Necesitas ayuda?</h2><p>Escríbenos y el equipo de soporte te responderá.</p></div>
        <Link to="/portal/ayuda" className="p-btn primario grande">Pedir ayuda</Link>
      </section>
    </div>
  )
}

const CATEGORIAS: [string, string][] = [
  ['otros', 'Una consulta general'], ['acceso_cuenta', 'Problema para entrar o con mi cuenta'], ['pagos_planes', 'Pagos o planes'],
  ['alertas_push', 'Avisos y alertas'], ['wearable', 'Pulsera o reloj (wearable)'], ['medicamentos', 'Medicamentos'],
]

export function Ayuda() {
  const { me } = usePortal()
  const [f, setF] = useState({ categoria: 'otros', asunto: '', descripcion: '' })
  const [hecho, setHecho] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setError(''); setEnviando(true)
    try { setHecho((await papi<{ mensaje: string }>('/ayuda', { method: 'POST', body: f })).mensaje) }
    catch (x) { setError(textoError(x)) } finally { setEnviando(false) }
  }
  const volver = me?.vistas[0] ? `/portal/${me.vistas[0]}` : '/portal'
  return (
    <div className="p-centrado">
      <section className="p-tarjeta angosta">
        <h1>Pedir ayuda</h1>
        <p className="p-sub">Tu mensaje llega al equipo de soporte de AgeCare como una solicitud (ticket).</p>
        {hecho ? <><div className="p-alerta ok">{hecho}</div><Link to={volver} className="p-btn primario grande">Volver al inicio</Link></> : (
          <form onSubmit={enviar} className="p-form">
            {error && <div className="p-alerta crit">{error}</div>}
            <label className="p-campo"><span>¿Sobre qué es?</span>
              <select value={f.categoria} onChange={e => setF({ ...f, categoria: e.target.value })}>
                {CATEGORIAS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </select></label>
            <label className="p-campo"><span>Asunto</span>
              <input value={f.asunto} onChange={e => setF({ ...f, asunto: e.target.value })} minLength={5} maxLength={160} required placeholder="Ej.: No veo los eventos" /></label>
            <label className="p-campo"><span>Cuéntanos qué pasa</span>
              <textarea value={f.descripcion} onChange={e => setF({ ...f, descripcion: e.target.value })} minLength={10} maxLength={2000} rows={5} required /></label>
            <button className="p-btn primario grande" disabled={enviando || f.asunto.trim().length < 5 || f.descripcion.trim().length < 10}>
              {enviando ? 'Enviando…' : 'Enviar a soporte'}</button>
            <Link to={volver} className="p-centro">Volver</Link>
          </form>
        )}
      </section>
    </div>
  )
}
