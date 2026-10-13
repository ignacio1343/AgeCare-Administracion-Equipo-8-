import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../auth'

export default function Login() {
  const { perfil, login } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [pideOtp, setPideOtp] = useState(false)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (perfil) return <Navigate to="/" replace />

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      await login(email, password, pideOtp ? otp : undefined)
      nav((loc.state as { desde?: string } | null)?.desde ?? '/', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'OTP_REQUIRED') {
        setPideOtp(true)
      } else {
        setError(err instanceof Error ? err.message : 'No se pudo iniciar sesión.')
        if (err instanceof ApiError && err.code === 'OTP_INVALID') setOtp('')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={enviar} noValidate>
        <div className="logo center">
          <div className="logo-mark">A</div>
          <div><div className="logo-name dark">AgeCare</div><div className="logo-sub">Consola de administración</div></div>
        </div>
        <h1>{pideOtp ? 'Verificación en dos pasos' : 'Iniciar sesión'}</h1>
        {!pideOtp ? (
          <>
            <label>Correo corporativo
              <input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
            </label>
            <label>Contraseña
              <input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
            </label>
          </>
        ) : (
          <label>Código de 6 dígitos de tu app autenticadora
            <input inputMode="numeric" pattern="\d{6}" maxLength={6} autoComplete="one-time-code" value={otp}
              onChange={e => setOtp(e.target.value.replace(/\D/g, ''))} autoFocus className="otp" />
          </label>
        )}
        {error && <div className="alert crit" role="alert">{error}</div>}
        <button className="btn primary block" disabled={enviando || !email || !password || (pideOtp && otp.length !== 6)}>
          {enviando ? 'Verificando…' : pideOtp ? 'Verificar' : 'Ingresar'}
        </button>
        {pideOtp && <button type="button" className="btn link" onClick={() => { setPideOtp(false); setOtp('') }}>Volver</button>}
        <p className="auth-foot">Acceso exclusivo para el equipo de Wellq Co. Toda acción queda registrada.</p>
      </form>
    </div>
  )
}
