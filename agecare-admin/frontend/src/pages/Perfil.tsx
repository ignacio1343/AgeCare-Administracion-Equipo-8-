import { useState, type FormEvent } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Card, ErrorBox, fechaHora } from '../components/ui'

export default function Perfil() {
  const { perfil, recargar } = useAuth()
  const [setup, setSetup] = useState<{ secreto: string; qr_svg: string } | null>(null)
  const [codigo, setCodigo] = useState('')
  const [error, setError] = useState<unknown>(null)
  if (!perfil) return null

  const iniciar = async () => {
    setError(null)
    try { setSetup(await api('/auth/mfa/configurar', { method: 'POST' })) } catch (e) { setError(e) }
  }
  const confirmar = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await api('/auth/mfa/confirmar', { method: 'POST', body: { codigo_otp: codigo } })
      setSetup(null)
      await recargar()
    } catch (err) { setError(err) }
  }

  return (
    <div className="grid g2">
      <Card title="Mi cuenta">
        <dl className="kv">
          <dt>Nombre</dt><dd>{perfil.nombre_completo}</dd>
          <dt>Correo</dt><dd>{perfil.email}</dd>
          <dt>Rol</dt><dd>{perfil.rol_nombre}</dd>
          <dt>Último acceso</dt><dd>{fechaHora(perfil.ultimo_acceso)}</dd>
          <dt>Módulos</dt><dd>{Object.entries(perfil.permisos).map(([m, n]) => <span key={m} className="chip neutral sm">{m} · {n === 'escritura' ? 'E' : 'L'}</span>)}</dd>
        </dl>
      </Card>
      <Card title="Segundo factor (TOTP)" sub={perfil.mfa_requerido ? 'Obligatorio para tu rol' : 'Opcional, recomendado'}>
        {perfil.mfa_habilitado ? (
          <div className="alert ok">✔ Activo. Al iniciar sesión se te pedirá el código de tu app autenticadora.</div>
        ) : !setup ? (
          <>
            <p className="muted">Usa Google Authenticator, Microsoft Authenticator u otra app compatible con TOTP.</p>
            <button className="btn primary" onClick={iniciar}>Configurar segundo factor</button>
          </>
        ) : (
          <form onSubmit={confirmar} className="mfa">
            <div className="qr" dangerouslySetInnerHTML={{ __html: setup.qr_svg }} />
            <div>
              <p>1. Escanea el código QR con tu app.</p>
              <p className="muted">¿No puedes escanear? Ingresa esta clave: <code>{setup.secreto}</code></p>
              <label>2. Escribe el código de 6 dígitos
                <input className="otp" inputMode="numeric" maxLength={6} value={codigo} onChange={e => setCodigo(e.target.value.replace(/\D/g, ''))} />
              </label>
              <button className="btn primary" disabled={codigo.length !== 6}>Activar</button>
            </div>
          </form>
        )}
        <ErrorBox error={error} />
      </Card>
    </div>
  )
}
