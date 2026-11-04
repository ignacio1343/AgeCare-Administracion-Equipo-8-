// Vista del representante: residentes y planes, pago con Webpay, registro del residente y estado en tiempo real.
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router'
import { clp, fecha, fechaHora } from '../components/ui'
import { ChecksClave, Campo, formatoRut, Pasos, rutValido } from './Acceso'
import { errorDeCampo, papi, textoError, type ItemResidente, type Notificacion, type PlanPortal, type RegistroVital, type Residente } from './api'
import { usePortal } from './auth'
import { Cargando } from './PortalApp'

export const ESTADO_VITAL: Record<string, { cls: string; ico: string }> = {
  normal: { cls: 'ok', ico: '🟢' }, alerta: { cls: 'warn', ico: '🟡' }, riesgoso: { cls: 'crit', ico: '🔴' },
}

export function ChipEstado({ r }: { r: RegistroVital }) {
  const e = ESTADO_VITAL[r.estado]
  return <span className={`p-chip ${e.cls}`}>{e.ico} {r.etiqueta}</span>
}

export function hace(s: string): string {
  const seg = Math.max(0, Math.round((Date.now() - new Date(s).getTime()) / 1000))
  if (seg < 60) return 'hace unos segundos'
  if (seg < 3600) return `hace ${Math.round(seg / 60)} min`
  if (seg < 86400) return `hace ${Math.round(seg / 3600)} h`
  return `hace ${Math.round(seg / 86400)} días`
}

export function irAWebpay(url: string, token: string) {
  // Webpay exige un formulario POST con token_ws (no un enlace). La política CSP permite form-action a Transbank.
  const f = document.createElement('form')
  f.method = 'POST'
  f.action = url
  const i = document.createElement('input')
  i.type = 'hidden'; i.name = 'token_ws'; i.value = token
  f.appendChild(i)
  document.body.appendChild(f)
  f.submit()
}

const ESTADO_SUS: Record<string, string> = { activa: 'Activo', en_mora: 'Pago pendiente', cancelada: 'Cancelado', vencida: 'Vencido' }

// ---------------------------------------------------------------- inicio
export function InicioRepresentante() {
  const { me, recargar } = usePortal()
  const loc = useLocation()
  const [items, setItems] = useState<ItemResidente[] | null>(null)
  const [riesgos, setRiesgos] = useState<Notificacion[]>([])
  const [error, setError] = useState('')
  const [cancelando, setCancelando] = useState<number | null>(null)
  const [motivo, setMotivo] = useState('')
  const [aviso, setAviso] = useState((loc.state as { aviso?: string } | null)?.aviso ?? '')

  const cargar = useCallback(() => {
    papi<ItemResidente[]>('/representante/residentes').then(setItems).catch(e => setError(textoError(e)))
    papi<{ items: Notificacion[] }>('/notificaciones')
      .then(r => setRiesgos(r.items.filter(n => !n.leida && (n.tipo === 'estado_riesgoso' || n.tipo === 'alerta_salud')))).catch(() => {})
  }, [])
  useEffect(() => { cargar(); const t = setInterval(cargar, 30_000); return () => clearInterval(t) }, [cargar])

  const cancelar = async (e: FormEvent, id: number) => {
    e.preventDefault()
    try {
      await papi(`/representante/suscripciones/${id}/cancelar`, { method: 'POST', body: { motivo } })
      setCancelando(null); setMotivo(''); setAviso('Plan cancelado.'); cargar()
    } catch (x) { setError(textoError(x)) }
  }
  const whatsapp = async (habilitado: boolean) => {
    try { await papi('/me/whatsapp', { method: 'PUT', body: { habilitado } }); await recargar() } catch (x) { setError(textoError(x)) }
  }
  const leerRiesgos = async () => { await papi('/notificaciones/leer', { method: 'POST' }); setRiesgos([]) }

  if (!items) return error ? <div className="p-alerta crit">{error}</div> : <Cargando />
  return (
    <>
      <div className="p-titulo">
        <div><h1>Hola, {me?.nombres ?? me?.nombre}</h1><p className="p-sub">Tus residentes, sus planes y su estado.</p></div>
        <Link to="/portal/representante/contratar" className="p-btn primario">＋ Agregar residente</Link>
      </div>
      {riesgos.map(n => (
        <div key={n.id_notificacion} className="p-alerta crit grande" role="alert">
          <b>{n.titulo}</b><p>{n.cuerpo}</p><small>{fechaHora(n.fecha_creacion)}</small>
          <div className="p-acciones-fila">
            {n.id_paciente && items.some(i => i.residente?.id_paciente === n.id_paciente && i.puede_ver_estado) && <Link className="p-btn sm blanco" to={`/portal/representante/residente/${n.id_paciente}`}>Ver estado</Link>}
            <button className="p-btn sm ghost" onClick={leerRiesgos}>Entendido</button>
          </div>
        </div>
      ))}
      {aviso && <div className="p-alerta ok" onClick={() => setAviso('')}>{aviso}</div>}
      {error && <div className="p-alerta crit">{error}</div>}
      {items.length === 0 && (
        <section className="p-tarjeta p-vacio">
          <div className="p-vacio-ico">👵</div>
          <h2>Aún no tienes residentes</h2>
          <p>Elige un plan, págalo con Webpay y luego registra los datos de tu familiar.</p>
          <Link to="/portal/representante/contratar" className="p-btn primario grande">Elegir plan</Link>
        </section>
      )}
      <div className="p-residentes">
        {items.map((it, k) => (
          <section key={it.id_suscripcion ?? `m${k}`} className={`p-tarjeta p-residente ${it.ultimo_estado ? ESTADO_VITAL[it.ultimo_estado.estado].cls : ''}`}>
            <div className="p-res-head">
              <div className="p-avatar">{it.residente ? it.residente.nombre.split(' ').map(x => x[0]).slice(0, 2).join('') : '＋'}</div>
              <div className="p-res-nombre">
                <h2>{it.residente?.nombre ?? 'Residente por registrar'}</h2>
                <small>{it.residente ? `${it.residente.edad ?? '—'} años · RUT ${it.residente.rut ?? '—'}` : 'El plan ya está pagado'}</small>
              </div>
              {it.plan && <span className={`p-plan ${it.plan.codigo_plan}`}>{it.plan.nombre}</span>}
            </div>
            <dl className="p-kv">
              <dt>Plan</dt><dd>{it.plan ? `${it.plan.nombre} · ${clp(it.plan.precio)}/mes` : 'Sin plan'} {it.estado_suscripcion && <em className={`p-est ${it.estado_suscripcion}`}>{ESTADO_SUS[it.estado_suscripcion] ?? it.estado_suscripcion}</em>}</dd>
              {it.fin_periodo && it.estado_suscripcion !== 'cancelada' && <><dt>Pagado hasta</dt><dd>{fecha(it.fin_periodo)}</dd></>}
              <dt>Avisos de riesgo</dt><dd>{it.recibe_avisos ? 'WhatsApp y portal' : 'No incluidos en el plan'}</dd>
              {it.puede_ver_estado && <><dt>Último estado</dt><dd>{it.ultimo_estado ? <><ChipEstado r={it.ultimo_estado} /> <small>{hace(it.ultimo_estado.fecha)}</small></> : 'Sin registros todavía'}</dd></>}
            </dl>
            <div className="p-acciones-fila">
              {!it.residente && it.estado_suscripcion === 'activa' && it.id_suscripcion &&
                <Link className="p-btn primario" to={`/portal/representante/plan/${it.id_suscripcion}/residente`}>Registrar residente</Link>}
              {it.residente && it.puede_ver_estado && <Link className="p-btn primario" to={`/portal/representante/residente/${it.residente.id_paciente}`}>Ver estado en tiempo real</Link>}
              {it.residente && !it.puede_ver_estado && it.estado_suscripcion !== 'cancelada' &&
                <span className="p-muted small">El estado en tiempo real está en los planes Platino y Proveedor.</span>}
              {it.puede_gestionar && it.estado_suscripcion !== 'cancelada' && it.id_suscripcion && <>
                <Link className="p-btn ghost" to={`/portal/representante/contratar?sus=${it.id_suscripcion}`}>Cambiar plan</Link>
                {it.plan && it.plan.precio > 0 && <Link className="p-btn ghost" to={`/portal/representante/contratar?sus=${it.id_suscripcion}&renovar=1`}>Pagar mes</Link>}
                <button className="p-btn ghost peligro" onClick={() => setCancelando(it.id_suscripcion)}>Cancelar plan</button>
              </>}
              {it.estado_suscripcion === 'cancelada' && it.residente &&
                <Link className="p-btn primario" to={`/portal/representante/contratar?paciente=${it.residente.id_paciente}`}>Contratar de nuevo</Link>}
            </div>
            {cancelando === it.id_suscripcion && it.id_suscripcion && (
              <form className="p-cancelar" onSubmit={e => cancelar(e, it.id_suscripcion!)}>
                <p><b>¿Cancelar el plan{it.residente ? ` de ${it.residente.nombre}` : ''}?</b> Dejará de recibir avisos y el estado en tiempo real.</p>
                <input value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Cuéntanos el motivo" minLength={5} required />
                <div className="p-acciones-fila">
                  <button className="p-btn peligro-lleno" disabled={motivo.trim().length < 5}>Sí, cancelar</button>
                  <button type="button" className="p-btn ghost" onClick={() => setCancelando(null)}>No</button>
                </div>
              </form>
            )}
          </section>
        ))}
      </div>
      <section className="p-tarjeta p-wa">
        <div>
          <h2>💬 Avisos por WhatsApp</h2>
          <p className="p-sub">Si el cuidador registra un estado <b>riesgoso</b>, te escribimos al {me?.telefono ?? 'teléfono registrado'} (planes Dorado, Platino y Proveedor).</p>
        </div>
        <label className="p-switch">
          <input type="checkbox" checked={!!me?.whatsapp_habilitado} onChange={e => whatsapp(e.target.checked)} />
          <span>{me?.whatsapp_habilitado ? 'Autorizado' : 'No autorizado'}</span>
        </label>
      </section>
    </>
  )
}

// ---------------------------------------------------------------- contratar, cambiar o renovar
export function Contratar() {
  const [q] = useSearchParams()
  const nav = useNavigate()
  const sus = q.get('sus') ? Number(q.get('sus')) : null
  const paciente = q.get('paciente') ? Number(q.get('paciente')) : null
  const renovar = q.get('renovar') === '1'
  const [planes, setPlanes] = useState<PlanPortal[]>([])
  const [actual, setActual] = useState<ItemResidente | null>(null)
  const [elegido, setElegido] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    papi<PlanPortal[]>('/planes').then(ps => { setPlanes(ps); setElegido(e => e || 'platino') }).catch(e => setError(textoError(e)))
    if (sus) papi<ItemResidente[]>('/representante/residentes').then(xs => {
      const it = xs.find(x => x.id_suscripcion === sus) ?? null
      setActual(it)
      if (renovar && it?.plan) setElegido(it.plan.codigo_plan)
    }).catch(() => {})
  }, [sus, renovar])

  const tipo = renovar ? 'renovacion' : sus ? 'cambio' : 'alta'
  const plan = planes.find(p => p.codigo_plan === elegido)
  const pagar = async () => {
    setError(''); setEnviando(true)
    try {
      const r = await papi<{ resultado: string; modo: string; url: string | null; token: string | null; id_suscripcion: number | null; mensaje: string }>(
        '/representante/pagos', { method: 'POST', body: { tipo, codigo_plan: elegido, id_suscripcion: sus, id_paciente: paciente } })
      if (r.resultado === 'listo') {
        if (tipo === 'alta' && !paciente && r.id_suscripcion) nav(`/portal/representante/plan/${r.id_suscripcion}/residente`)
        else nav('/portal/representante', { state: { aviso: r.mensaje } })
      } else if (r.modo === 'webpay' && r.url && r.token) {
        irAWebpay(r.url, r.token)
      } else if (r.url) nav(r.url)
    } catch (x) { setError(textoError(x)); setEnviando(false) }
  }

  const titulo = renovar ? 'Pagar el mes' : sus ? 'Cambiar plan' : paciente ? 'Contratar de nuevo' : 'Elige el plan de tu residente'
  return (
    <>
      {q.get('bienvenida') && <Pasos actual={3} />}
      <div className="p-titulo"><div><h1>{titulo}</h1>
        <p className="p-sub">{actual?.residente ? `Para ${actual.residente.nombre}. ` : ''}El pago es mensual y se hace en Webpay de Transbank (débito o crédito).</p></div></div>
      {error && <div className="p-alerta crit">{error}</div>}
      <div className="p-planes" role="radiogroup" aria-label="Planes">
        {planes.map(p => {
          const esActual = actual?.plan?.codigo_plan === p.codigo_plan
          const bloqueado = renovar ? !esActual : !!sus && esActual
          return (
            <button key={p.codigo_plan} role="radio" aria-checked={elegido === p.codigo_plan} disabled={bloqueado}
                    className={`p-plan-card ${p.codigo_plan}${elegido === p.codigo_plan ? ' sel' : ''}`} onClick={() => setElegido(p.codigo_plan)}>
              {p.codigo_plan === 'platino' && <span className="p-reco">Recomendado</span>}
              {esActual && <span className="p-reco gris">Plan actual</span>}
              <h3>{p.nombre}</h3>
              <div className="p-precio">{p.precio ? clp(p.precio) : 'Gratis'}<small>{p.precio ? '/mes' : ''}</small></div>
              <ul>
                <li className={p.incluye_estado_tiempo_real ? 'si' : 'no'}>Estado vital en tiempo real</li>
                <li className={p.incluye_avisos_riesgo ? 'si' : 'no'}>Aviso por WhatsApp y en el portal si está en riesgo</li>
                <li className="si">Chistes, noticias y eventos para el residente</li>
                <li className="si">Ayuda de soporte</li>
              </ul>
            </button>
          )
        })}
      </div>
      <div className="p-pagar">
        <div>
          <b>{plan ? `${plan.nombre}: ${plan.precio ? `${clp(plan.precio)} por 30 días` : 'sin costo'}` : 'Elige un plan'}</b>
          <small>{plan?.precio ? 'Serás redirigido a Webpay para pagar. Al volver, el plan queda activo.' : 'Se activa de inmediato.'}</small>
        </div>
        <button className="p-btn primario grande" onClick={pagar} disabled={!plan || enviando}>
          {enviando ? 'Conectando con Webpay…' : plan?.precio ? `Pagar ${clp(plan.precio)} con Webpay` : 'Activar plan'}
        </button>
      </div>
      <Link to="/portal/representante" className="p-volver">← Volver a mis residentes</Link>
    </>
  )
}

// ---------------------------------------------------------------- registrar residente
export function NuevoResidente() {
  const { id } = useParams()
  const nav = useNavigate()
  const [f, setF] = useState({ rut: '', primer_nombre: '', primer_apellido: '', segundo_apellido: '', email: '', fecha_nacimiento: '', password: '', password2: '' })
  const [err, setErr] = useState<unknown>(null)
  const [enviando, setEnviando] = useState(false)
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })
  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setErr(null); setEnviando(true)
    try {
      const r = await papi<ItemResidente>(`/representante/suscripciones/${id}/residente`, { method: 'POST', body: { ...f, segundo_apellido: f.segundo_apellido || null } })
      nav('/portal/representante', { state: { aviso: `${r.residente?.nombre} quedó registrado. Ya puede entrar al portal con su correo o RUT y la contraseña que elegiste.` } })
    } catch (x) { setErr(x); setEnviando(false) }
  }
  const rutMal = f.rut.length >= 9 && !rutValido(f.rut)
  return (
    <>
      <Pasos actual={4} />
      <section className="p-tarjeta">
        <h1>Datos de tu residente</h1>
        <p className="p-sub">Con su correo (o RUT) y esta contraseña, tu familiar entra a su propia vista para ver chistes, noticias y eventos.</p>
        <form onSubmit={enviar} className="p-form p-grid2">
          {err !== null && <div className="p-alerta crit full">{textoError(err)}</div>}
          <Campo label="RUT" error={rutMal ? 'Revisa el número y el dígito verificador' : errorDeCampo(err, 'rut')}>
            <input value={f.rut} onChange={e => setF({ ...f, rut: formatoRut(e.target.value) })} placeholder="4.876.543-2" required />
          </Campo>
          <Campo label="Primer nombre" error={errorDeCampo(err, 'primer_nombre')}><input value={f.primer_nombre} onChange={set('primer_nombre')} required /></Campo>
          <Campo label="Primer apellido" error={errorDeCampo(err, 'primer_apellido')}><input value={f.primer_apellido} onChange={set('primer_apellido')} required /></Campo>
          <Campo label="Segundo apellido"><input value={f.segundo_apellido} onChange={set('segundo_apellido')} /></Campo>
          <Campo label="Correo" error={errorDeCampo(err, 'email')}><input type="email" value={f.email} onChange={set('email')} required /></Campo>
          <Campo label="Fecha de nacimiento" error={errorDeCampo(err, 'fecha_nacimiento')}>
            <input type="date" value={f.fecha_nacimiento} onChange={set('fecha_nacimiento')} max={new Date().toISOString().slice(0, 10)} required />
          </Campo>
          <Campo label="Contraseña del residente"><input type="password" value={f.password} onChange={set('password')} autoComplete="new-password" required /></Campo>
          <Campo label="Repite la contraseña"><input type="password" value={f.password2} onChange={set('password2')} autoComplete="new-password" required /></Campo>
          <div className="full"><ChecksClave clave={f.password} clave2={f.password2} /></div>
          <div className="full p-acciones">
            <button className="p-btn primario grande" disabled={enviando || !rutValido(f.rut)}>{enviando ? 'Guardando…' : 'Registrar residente'}</button>
          </div>
        </form>
      </section>
    </>
  )
}

// ---------------------------------------------------------------- estado en tiempo real (Platino y Proveedor)
interface EstadoVital { residente: Residente; plan: string | null; actual: RegistroVital | null; historial: RegistroVital[]; consultado: string; actualizar_cada_seg: number }

export function EstadoResidente() {
  const { id } = useParams()
  const [d, setD] = useState<EstadoVital | null>(null)
  const [error, setError] = useState('')
  const [, setTick] = useState(0)
  const cargar = useCallback(() => {
    papi<EstadoVital>(`/representante/residentes/${id}/estado`).then(x => { setD(x); setError('') }).catch(e => setError(textoError(e)))
  }, [id])
  useEffect(() => {
    cargar()
    const t = setInterval(cargar, 15_000)          // «tiempo real»: se actualiza solo cada 15 segundos
    const r = setInterval(() => setTick(x => x + 1), 5_000)
    return () => { clearInterval(t); clearInterval(r) }
  }, [cargar])
  if (error && !d) return <><div className="p-alerta crit">{error}</div><Link to="/portal/representante" className="p-volver">← Volver</Link></>
  if (!d) return <Cargando />
  const a = d.actual
  return (
    <>
      <div className="p-titulo"><div><h1>{d.residente.nombre}</h1><p className="p-sub">{d.residente.edad} años · Estado vital en tiempo real</p></div>
        <span className="p-vivo" title="Se actualiza cada 15 segundos"><i />En vivo · {hace(d.consultado)}</span></div>
      {a ? (
        <section className={`p-estado ${ESTADO_VITAL[a.estado].cls}`} aria-live="polite">
          <div className="p-estado-ico">{ESTADO_VITAL[a.estado].ico}</div>
          <div>
            <small>Estado actual</small>
            <h2>{a.etiqueta}</h2>
            <p className="p-obs">“{a.observacion}”</p>
            <p className="p-meta">Registrado por <b>{a.cuidador}</b> · {fechaHora(a.fecha)} ({hace(a.fecha)})</p>
          </div>
        </section>
      ) : <section className="p-tarjeta p-vacio"><p>El cuidador todavía no registra el estado de {d.residente.nombre}.</p></section>}
      {d.historial.length > 1 && (
        <section className="p-tarjeta">
          <h2>Últimos registros</h2>
          <ol className="p-historial">
            {d.historial.map(r => (
              <li key={r.id_registro}><ChipEstado r={r} /><div><p>{r.observacion}</p><small>{r.cuidador} · {fechaHora(r.fecha)}</small></div></li>
            ))}
          </ol>
        </section>
      )}
      <Link to="/portal/representante" className="p-volver">← Volver a mis residentes</Link>
    </>
  )
}
