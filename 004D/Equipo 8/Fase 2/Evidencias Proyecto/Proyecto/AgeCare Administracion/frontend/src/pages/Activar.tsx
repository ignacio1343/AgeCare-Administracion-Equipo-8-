import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'

export default function Activar() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [info, setInfo] = useState<{ nombre_completo: string; email: string; mfa_requerido: boolean } | null>(null)
  const [error, setError] = useState('')
  const [p1, setP1] = useState('')
  const [p2, setP2] = useState('')
  const [listo, setListo] = useState(false)

  useEffect(() => {
    api(`/auth/activacion/${encodeURIComponent(token)}`).then(setInfo).catch(e => setError(e.message))
  }, [token])

  const valida = p1.length >= 8 && /[a-zA-Z]/.test(p1) && /\d/.test(p1)
  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await api('/auth/activacion', { method: 'POST', body: { token, password: p1 } })
      setListo(true)
    } catch (err) { setError(err instanceof Error ? err.message : 'Error') }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={enviar}>
        <div className="logo center"><div className="logo-mark">A</div><div><div className="logo-name dark">AgeCare</div><div className="logo-sub">Activar cuenta</div></div></div>
        {listo ? (
          <>
            <h1>Cuenta activada</h1>
            <p>Ya puedes ingresar con tu correo y la contraseña que definiste.{info?.mfa_requerido && ' Al entrar, configura tu segundo factor en «Mi cuenta».'}</p>
            <Link className="btn primary block" to="/login">Ir al inicio de sesión</Link>
          </>
        ) : !info ? (
          <>{error ? <div className="alert crit">{error}</div> : <p>Validando enlace…</p>}</>
        ) : (
          <>
            <h1>Hola, {info.nombre_completo.split(' ')[0]}</h1>
            <p className="muted">Define la contraseña de <b>{info.email}</b>.</p>
            <label>Nueva contraseña<input type="password" autoComplete="new-password" value={p1} onChange={e => setP1(e.target.value)} /></label>
            <label>Repite la contraseña<input type="password" autoComplete="new-password" value={p2} onChange={e => setP2(e.target.value)} /></label>
            <ul className="checks">
              <li className={p1.length >= 8 ? 'ok' : ''}>Al menos 8 caracteres</li>
              <li className={/[a-zA-Z]/.test(p1) && /\d/.test(p1) ? 'ok' : ''}>Letras y números</li>
              <li className={p1 && p1 === p2 ? 'ok' : ''}>Ambas coinciden</li>
            </ul>
            {error && <div className="alert crit">{error}</div>}
            <button className="btn primary block" disabled={!valida || p1 !== p2}>Activar cuenta</button>
          </>
        )}
      </form>
    </div>
  )
}
