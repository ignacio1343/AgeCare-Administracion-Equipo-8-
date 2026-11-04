// Ingreso, registro del representante con código SMS, «¿Olvidaste tu contraseña?» y cambio de clave.
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { errorDeCampo, papi, textoError, type Me } from './api'
import { usePortal } from './auth'
import { Marca } from './PortalApp'

const INICIO: Record<string, string> = { representante: '/portal/representante', residente: '/portal/residente', cuidador: '/portal/cuidador' }

export function PaginaAcceso({ titulo, sub, children, ancho = false }: { titulo: string; sub?: ReactNode; children: ReactNode; ancho?: boolean }) {
  return (
    <div className="p-acceso">
      <div className={`p-acceso-card${ancho ? ' ancho' : ''}`}>
        <Marca />
        <h1>{titulo}</h1>
        {sub && <p className="p-sub">{sub}</p>}
        {children}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- RUT: formato y dígito verificador (módulo 11)
export function formatoRut(v: string): string {
  const limpio = v.replace(/[^0-9kK]/g, '').toUpperCase().slice(0, 9)
  if (limpio.length < 2) return limpio
  const cuerpo = limpio.slice(0, -1).replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `${cuerpo}-${limpio.slice(-1)}`
}
export function rutValido(v: string): boolean {
  const r = v.replace(/[^0-9kK]/g, '').toUpperCase()
  if (!/^\d{7,8}[\dK]$/.test(r)) return false
  let s = 0, m = 2
  for (const d of r.slice(0, -1).split('').reverse()) { s += Number(d) * m; m = m === 7 ? 2 : m + 1 }
  const res = 11 - (s % 11)
  return r.slice(-1) === (res === 11 ? '0' : res === 10 ? 'K' : String(res))
}

export function ChecksClave({ clave, clave2 }: { clave: string; clave2: string }) {
  const reglas: [boolean, string][] = [
    [clave.length >= 8, 'Al menos 8 caracteres'], [/[A-Za-zÁÉÍÓÚáéíóúÑñ]/.test(clave), 'Letras'], [/\d/.test(clave), 'Números'],
    [clave.length > 0 && clave === clave2, 'Las dos contraseñas coinciden'],
  ]
  return <ul className="p-checks">{reglas.map(([ok, t]) => <li key={t} className={ok ? 'ok' : ''}>{t}</li>)}</ul>
}
const claveOk = (a: string, b: string) => a.length >= 8 && /[A-Za-zÁÉÍÓÚáéíóúÑñ]/.test(a) && /\d/.test(a) && a === b

export function Campo({ label, error, hint, children }: { label: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <label className={`p-campo${error ? ' con-error' : ''}`}>
      <span>{label}</span>
      {children}
      {error ? <small className="p-error-campo">{error}</small> : hint ? <small>{hint}</small> : null}
    </label>
  )
}

// ---------------------------------------------------------------- ingresar
export function Ingresar() {
  const { entrar, me } = usePortal()
  const nav = useNavigate()
  const loc = useLocation()
  const [usuario, setUsuario] = useState('')
  const [clave, setClave] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  useEffect(() => { if (me) nav('/portal', { replace: true }) }, [me, nav])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setError(''); setEnviando(true)
    try {
      const m: Me = await entrar(usuario.trim(), clave)
      const desde = (loc.state as { desde?: string } | null)?.desde
      nav(m.debe_cambiar_password ? '/portal/cambiar-clave' : desde ?? INICIO[m.vistas[0]] ?? '/portal', { replace: true })
    } catch (err) { setError(textoError(err)) } finally { setEnviando(false) }
  }
  return (
    <PaginaAcceso titulo="Ingresar" sub="Representantes, residentes y cuidadores">
      <form onSubmit={enviar} className="p-form">
        {error && <div className="p-alerta crit" role="alert">{error}</div>}
        <Campo label="Correo o RUT">
          <input value={usuario} onChange={e => setUsuario(e.target.value)} autoComplete="username" required autoFocus
                 placeholder="tu@correo.cl o 12.345.678-5" />
        </Campo>
        <Campo label="Contraseña">
          <input type="password" value={clave} onChange={e => setClave(e.target.value)} autoComplete="current-password" required />
        </Campo>
        <button className="p-btn primario grande" disabled={enviando}>{enviando ? 'Ingresando…' : 'Ingresar'}</button>
        <Link to="/portal/olvide" className="p-centro">¿Olvidaste tu contraseña?</Link>
      </form>
      <div className="p-separador"><span>¿Eres familiar de un adulto mayor?</span></div>
      <Link to="/portal/registro" className="p-btn ghost grande">Crear cuenta de representante</Link>
    </PaginaAcceso>
  )
}

// ---------------------------------------------------------------- registro (2 pasos)
interface Pais { codigo: string; prefijo: string; nombre: string; ejemplo: string }
interface Verificacion { verificacion: string; telefono: string; modo: string; codigo_demo: string | null; reenviar_en_seg: number; intentos_restantes: number }
interface Legal { tipo_documento: string; version: string; contenido: string }

export function Registro() {
  const { conTokens } = usePortal()
  const nav = useNavigate()
  const [paises, setPaises] = useState<Pais[]>([])
  const [legales, setLegales] = useState<Legal[]>([])
  const [verLegal, setVerLegal] = useState<Legal | null>(null)
  const [f, setF] = useState({ email: '', rut: '', nombres: '', primer_apellido: '', segundo_apellido: '', pais: 'CL', telefono: '',
                              password: '', password2: '', acepta_terminos: false, acepta_whatsapp: true })
  const [err, setErr] = useState<unknown>(null)
  const [enviando, setEnviando] = useState(false)
  const [v, setV] = useState<Verificacion | null>(null)
  const [codigo, setCodigo] = useState('')
  const [espera, setEspera] = useState(0)

  useEffect(() => {
    papi<Pais[]>('/paises').then(setPaises).catch(() => {})
    papi<Legal[]>('/legales').then(setLegales).catch(() => {})
  }, [])
  useEffect(() => {
    if (espera <= 0) return
    const t = setTimeout(() => setEspera(s => s - 1), 1000)
    return () => clearTimeout(t)
  }, [espera])

  const pais = paises.find(p => p.codigo === f.pais)
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value })
  const rutMal = f.rut.length >= 9 && !rutValido(f.rut)
  const listo = f.email && rutValido(f.rut) && f.nombres && f.primer_apellido && f.telefono && claveOk(f.password, f.password2) && f.acepta_terminos

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setErr(null); setEnviando(true)
    try {
      const r = await papi<Verificacion>('/registro', { method: 'POST', body: { ...f, segundo_apellido: f.segundo_apellido || null } })
      setV(r); setEspera(r.reenviar_en_seg); setCodigo('')
    } catch (x) { setErr(x) } finally { setEnviando(false) }
  }
  const confirmar = async (e: FormEvent) => {
    e.preventDefault()
    if (!v) return
    setErr(null); setEnviando(true)
    try {
      const r = await papi<{ access_token: string; usuario: Me }>('/registro/confirmar', { method: 'POST', body: { verificacion: v.verificacion, codigo } })
      conTokens(r.access_token, r.usuario)
      nav('/portal/representante/contratar?bienvenida=1', { replace: true })
    } catch (x) {
      setErr(x)
      const d = (x as { details?: { intentos_restantes?: number } }).details
      if (d?.intentos_restantes !== undefined) setV({ ...v, intentos_restantes: d.intentos_restantes })
      if ((x as { status?: number }).status === 410 || (x as { code?: string }).code === 'CODE_ATTEMPTS_EXCEEDED') setTimeout(() => setV(null), 2500)
    } finally { setEnviando(false) }
  }
  const reenviar = async () => {
    if (!v) return
    setErr(null)
    try { const r = await papi<Verificacion>('/registro/reenviar', { method: 'POST', body: { verificacion: v.verificacion } }); setV(r); setEspera(r.reenviar_en_seg) }
    catch (x) { setErr(x) }
  }

  if (v) {
    return (
      <PaginaAcceso titulo="Confirma tu teléfono" sub={<>Te enviamos un código de 6 dígitos por SMS al <b>{v.telefono}</b>.</>}>
        <Pasos actual={2} />
        <form onSubmit={confirmar} className="p-form">
          {v.modo === 'simulado' && v.codigo_demo && (
            <div className="p-alerta info"><b>Modo demostración:</b> no se envió un SMS real. Tu código es <code className="p-codigo">{v.codigo_demo}</code></div>
          )}
          {err !== null && <div className="p-alerta crit" role="alert">{textoError(err)}</div>}
          <Campo label="Código de verificación" hint={`Te quedan ${v.intentos_restantes} intento${v.intentos_restantes === 1 ? '' : 's'}. El código vence en 10 minutos.`}>
            <input className="p-otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={codigo} autoFocus
                   onChange={e => setCodigo(e.target.value.replace(/\D/g, ''))} required />
          </Campo>
          <button className="p-btn primario grande" disabled={enviando || codigo.length !== 6}>{enviando ? 'Verificando…' : 'Confirmar y crear cuenta'}</button>
          <div className="p-fila-centro">
            <button type="button" className="p-link" disabled={espera > 0} onClick={reenviar}>
              {espera > 0 ? `Reenviar código en ${espera} s` : 'Reenviar código'}
            </button>
            <button type="button" className="p-link" onClick={() => { setV(null); setErr(null) }}>Corregir mis datos</button>
          </div>
        </form>
      </PaginaAcceso>
    )
  }

  return (
    <PaginaAcceso ancho titulo="Crear cuenta de representante"
                  sub="Con tu cuenta contratas el plan de tu familiar, lo registras y recibes avisos si su salud está en riesgo.">
      <Pasos actual={1} />
      <form onSubmit={enviar} className="p-form p-grid2">
        {err !== null && <div className="p-alerta crit full" role="alert">{textoError(err)}</div>}
        <Campo label="Nombres" error={errorDeCampo(err, 'nombres')}><input value={f.nombres} onChange={set('nombres')} autoComplete="given-name" required /></Campo>
        <Campo label="RUT" error={rutMal ? 'Revisa el número y el dígito verificador' : errorDeCampo(err, 'rut')}>
          <input value={f.rut} onChange={e => setF({ ...f, rut: formatoRut(e.target.value) })} placeholder="12.345.678-5" required inputMode="text" />
        </Campo>
        <Campo label="Primer apellido" error={errorDeCampo(err, 'primer_apellido')}><input value={f.primer_apellido} onChange={set('primer_apellido')} autoComplete="family-name" required /></Campo>
        <Campo label="Segundo apellido" error={errorDeCampo(err, 'segundo_apellido')}><input value={f.segundo_apellido} onChange={set('segundo_apellido')} /></Campo>
        <Campo label="Correo" error={errorDeCampo(err, 'email')}><input type="email" value={f.email} onChange={set('email')} autoComplete="email" required /></Campo>
        <Campo label="Teléfono celular" error={errorDeCampo(err, 'telefono')} hint={pais ? `Ejemplo: ${pais.prefijo} ${pais.ejemplo}` : undefined}>
          <div className="p-telefono">
            <select value={f.pais} onChange={set('pais')} aria-label="País">
              {paises.map(p => <option key={p.codigo} value={p.codigo}>{p.nombre} ({p.prefijo})</option>)}
            </select>
            <input value={f.telefono} onChange={set('telefono')} inputMode="tel" autoComplete="tel-national" required placeholder={pais?.ejemplo} />
          </div>
        </Campo>
        <Campo label="Contraseña"><input type="password" value={f.password} onChange={set('password')} autoComplete="new-password" required /></Campo>
        <Campo label="Repite la contraseña"><input type="password" value={f.password2} onChange={set('password2')} autoComplete="new-password" required /></Campo>
        <div className="full"><ChecksClave clave={f.password} clave2={f.password2} /></div>
        <label className="p-check full">
          <input type="checkbox" checked={f.acepta_terminos} onChange={set('acepta_terminos')} />
          <span>Acepto los {legales.length ? legales.map((l, i) => (
            <span key={l.tipo_documento}>{i > 0 && ' y la '}<button type="button" className="p-link" onClick={() => setVerLegal(l)}>
              {l.tipo_documento === 'terminos' ? 'términos y condiciones' : 'política de privacidad'}</button></span>)) : 'términos y la política de privacidad'} (Ley 19.628).</span>
        </label>
        <label className="p-check full">
          <input type="checkbox" checked={f.acepta_whatsapp} onChange={set('acepta_whatsapp')} />
          <span>Autorizo recibir por WhatsApp avisos cuando el estado de salud de mi residente sea <b>riesgoso</b> (planes Dorado, Platino y Proveedor). Puedo retirarlo cuando quiera.</span>
        </label>
        <div className="full p-acciones">
          <button className="p-btn primario grande" disabled={!listo || enviando}>{enviando ? 'Enviando código…' : 'Continuar: enviar código por SMS'}</button>
          <Link to="/portal/ingresar" className="p-centro">Ya tengo cuenta</Link>
        </div>
      </form>
      {verLegal && (
        <div className="p-modal" role="dialog" aria-modal="true" onClick={() => setVerLegal(null)}>
          <div className="p-modal-card" onClick={e => e.stopPropagation()}>
            <h2>{verLegal.tipo_documento === 'terminos' ? 'Términos y condiciones' : 'Política de privacidad'} v{verLegal.version}</h2>
            <div className="p-legal">{verLegal.contenido}</div>
            <button className="p-btn primario" onClick={() => setVerLegal(null)}>Cerrar</button>
          </div>
        </div>
      )}
    </PaginaAcceso>
  )
}

function Pasos({ actual }: { actual: number }) {
  const pasos = ['Tus datos', 'Código SMS', 'Plan y pago', 'Tu residente']
  return (
    <ol className="p-pasos" aria-label="Pasos del registro">
      {pasos.map((p, i) => <li key={p} className={i + 1 < actual ? 'hecho' : i + 1 === actual ? 'actual' : ''}><span>{i + 1}</span>{p}</li>)}
    </ol>
  )
}
export { Pasos }

// ---------------------------------------------------------------- ¿olvidaste tu contraseña?
export function Olvide() {
  const [usuario, setUsuario] = useState('')
  const [detalle, setDetalle] = useState('')
  const [hecho, setHecho] = useState('')
  const [error, setError] = useState('')
  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try { setHecho((await papi<{ mensaje: string }>('/auth/olvide', { method: 'POST', body: { usuario, detalle: detalle || null } })).mensaje) }
    catch (x) { setError(textoError(x)) }
  }
  return (
    <PaginaAcceso titulo="¿Olvidaste tu contraseña?" sub="Escribe tu correo o RUT. Se crea una solicitud para nuestro equipo de soporte, que te contactará para darte una clave nueva.">
      {hecho ? (
        <><div className="p-alerta ok">{hecho}</div><Link to="/portal/ingresar" className="p-btn primario grande">Volver a ingresar</Link></>
      ) : (
        <form onSubmit={enviar} className="p-form">
          {error && <div className="p-alerta crit">{error}</div>}
          <Campo label="Correo o RUT"><input value={usuario} onChange={e => setUsuario(e.target.value)} required autoFocus /></Campo>
          <Campo label="Comentario (opcional)" hint="Por ejemplo, a qué hora prefieres que te llamen.">
            <textarea value={detalle} onChange={e => setDetalle(e.target.value)} maxLength={500} rows={3} />
          </Campo>
          <button className="p-btn primario grande" disabled={usuario.trim().length < 3}>Pedir ayuda a soporte</button>
          <Link to="/portal/ingresar" className="p-centro">Volver</Link>
        </form>
      )}
    </PaginaAcceso>
  )
}

// ---------------------------------------------------------------- cambiar contraseña (obligatorio con clave temporal)
export function Cambiar() {
  const { me, recargar } = usePortal()
  const nav = useNavigate()
  const [f, setF] = useState({ actual: '', password: '', password2: '' })
  const [error, setError] = useState('')
  const [ok, setOk] = useState(false)
  const temporal = me?.debe_cambiar_password
  const listo = useMemo(() => f.actual && claveOk(f.password, f.password2), [f])
  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await papi('/auth/cambiar-password', { method: 'POST', body: f })
      await recargar()
      setOk(true)
      setTimeout(() => nav('/portal', { replace: true }), 1200)
    } catch (x) { setError(textoError(x)) }
  }
  return (
    <div className="p-centrado">
      <section className="p-tarjeta angosta">
        <h1>{temporal ? 'Crea tu contraseña' : 'Cambiar contraseña'}</h1>
        {temporal && <p className="p-sub">Entraste con una clave temporal que te entregó soporte. Elige una nueva para continuar.</p>}
        {ok ? <div className="p-alerta ok">Contraseña actualizada.</div> : (
          <form onSubmit={enviar} className="p-form">
            {error && <div className="p-alerta crit">{error}</div>}
            <Campo label={temporal ? 'Clave temporal' : 'Contraseña actual'}><input type="password" value={f.actual} onChange={e => setF({ ...f, actual: e.target.value })} autoComplete="current-password" required /></Campo>
            <Campo label="Nueva contraseña"><input type="password" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} autoComplete="new-password" required /></Campo>
            <Campo label="Repite la nueva contraseña"><input type="password" value={f.password2} onChange={e => setF({ ...f, password2: e.target.value })} autoComplete="new-password" required /></Campo>
            <ChecksClave clave={f.password} clave2={f.password2} />
            <button className="p-btn primario grande" disabled={!listo}>Guardar contraseña</button>
          </form>
        )}
      </section>
    </div>
  )
}
